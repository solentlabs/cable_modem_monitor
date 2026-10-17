"""Auto-detect — narrow the catalog choice from a device's landing page.

``detect()`` sweeps the catalog's ``default_host`` addresses with one
credential-free ``GET /`` each and reports which catalog names the
landing page carries. ``match_page()`` is the pure matcher both the
sweep and the intake accuracy report call. Nothing here selects a modem,
a variant or an auth strategy; the user confirms the result.

Synchronous and blocking: async consumers call ``detect()`` in an
executor.

See DETECTION_SPEC.md.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from .catalog_manager import ModemSummary
from .connectivity import create_session, is_connectivity_error
from .orchestration.events import DetectionMatched, DetectionProbeResult
from .orchestration.logging import log_event

_logger = logging.getLogger(__name__)

# DETECTION_SPEC.md § Sweep
_MAX_REDIRECTS = 5
_BODY_CAP = 256 * 1024
_CHUNK = 8 * 1024
_MAX_WORKERS = 32

# DETECTION_SPEC.md § Matching: runs of [a-z0-9], ASCII only so a name
# never matches through a look-alike character.
_TOKEN = re.compile(r"[A-Za-z0-9]+")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_PASSWORD_INPUT = re.compile(r"<input\b[^>]*\btype\s*=\s*[\"']?password\b", re.IGNORECASE)


@dataclass(frozen=True)
class Observation:
    """What a host's landing response looked like; evidence for the user, never read by the matcher."""

    scheme: str
    status: int
    final_path: str
    server: str | None
    title: str | None
    www_authenticate: str | None
    password_field: bool


@dataclass(frozen=True)
class PageMatch:
    """The catalog entries and names a page carries."""

    models: list[ModemSummary]
    buckets: list[str]
    matched: list[str]


@dataclass(frozen=True)
class Detection:
    """One answering address with what it showed and which catalog names its page carries."""

    host: str
    observation: Observation
    match: PageMatch


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _name_tokens(name: str) -> tuple[str, ...]:
    return tuple(m.group().lower() for m in _TOKEN.finditer(name))


class _Page:
    """A page's tokens, with a lookup for where a catalog name first appears as a consecutive run."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.spans = [(m.group().lower(), m.start(), m.end()) for m in _TOKEN.finditer(text)]
        self._starts: dict[str, list[int]] = {}
        for position, (word, _, _) in enumerate(self.spans):
            self._starts.setdefault(word, []).append(position)
        # Token run -> position of its first occurrence, for every name found so far.
        self.first_hit: dict[tuple[str, ...], int] = {}

    def names(self, name: str) -> bool:
        """True when ``name`` is a consecutive token run on the page; remembers where it first is."""
        tokens = _name_tokens(name)
        if not tokens:
            return False
        if tokens in self.first_hit:
            return True
        for position in self._starts.get(tokens[0], []):
            run = self.spans[position : position + len(tokens)]
            if len(run) == len(tokens) and all(word == token for (word, _, _), token in zip(run, tokens, strict=True)):
                self.first_hit[tokens] = position
                return True
        return False

    def spellings(self) -> list[str]:
        """The found names as the page spells them, in page order, one per distinct name."""
        found = sorted(self.first_hit.items(), key=lambda item: item[1])
        return [self.text[self.spans[pos][1] : self.spans[pos + len(tokens) - 1][2]] for tokens, pos in found]


def match_page(text: str, summaries: list[ModemSummary]) -> PageMatch:
    """Return the catalog entries and maker or brand names that ``text`` names."""
    page = _Page(text)

    # A list, not a generator: every name an entry carries is recorded for `matched`, not just the first hit.
    models = [s for s in summaries if any([page.names(name) for name in (s.model, *s.model_aliases)])]

    buckets: list[str] = []
    seen_buckets: set[tuple[str, ...]] = set()
    for summary in summaries:
        for name in (summary.manufacturer, *summary.brands):
            tokens = _name_tokens(name)
            if tokens not in seen_buckets and page.names(name):
                seen_buckets.add(tokens)
                buckets.append(name)

    return PageMatch(models=models, buckets=buckets, matched=page.spellings())


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


def _sweep_hosts(summaries: list[ModemSummary]) -> list[str]:
    """Distinct ``default_host`` values, most frequent first, then lexical."""
    counts = Counter(s.default_host for s in summaries)
    return sorted(counts, key=lambda host: (-counts[host], host))


@dataclass
class _Probe:
    """One host's outcome: an observation and the page text, or the reason it did not answer."""

    host: str
    observation: Observation | None = None
    text: str = ""
    reason: str | None = None


def _read_capped(response: requests.Response, deadline: float) -> bytes:
    """Read the body up to the byte cap, or until the deadline passes."""
    body = bytearray()
    for chunk in response.iter_content(_CHUNK):
        body += chunk
        if len(body) >= _BODY_CAP or time.monotonic() > deadline:
            break
    return bytes(body[:_BODY_CAP])


def describe_response(url: str, status: int, headers: Mapping[str, str], body: bytes) -> tuple[Observation, str]:
    """Return a landing response's observation and the text the matcher reads (``Server`` header, then body)."""
    lowered = {name.lower(): value for name, value in headers.items()}
    text = body[:_BODY_CAP].decode("utf-8", errors="replace")
    title_match = _TITLE.search(text)
    title = " ".join(title_match.group(1).split()) if title_match else ""
    parsed = urlparse(url)
    observation = Observation(
        scheme=parsed.scheme,
        status=status,
        final_path=parsed.path or "/",
        server=lowered.get("server"),
        title=title or None,
        www_authenticate=lowered.get("www-authenticate"),
        password_field=bool(_PASSWORD_INPUT.search(text)),
    )
    return observation, f"{observation.server or ''}\n{text}"


def _probe(host: str, timeout: float) -> _Probe:
    """Send one credential-free ``GET /``: http first, https when http yields no HTTP response."""
    session = create_session()
    # Environment netrc and proxies would add credentials or reroute a LAN probe.
    session.trust_env = False
    session.max_redirects = _MAX_REDIRECTS
    try:
        for scheme in ("http", "https"):
            try:
                with session.get(f"{scheme}://{host}/", timeout=timeout, stream=True) as response:
                    body = _read_capped(response, time.monotonic() + timeout)
                    observation, text = describe_response(response.url, response.status_code, response.headers, body)
                    return _Probe(host, observation, text)
            except requests.RequestException as exc:
                # No HTTP response at all: the only case the other scheme can answer.
                # A refusal, an error status or a redirect loop is an answer or a verdict.
                if scheme == "http" and is_connectivity_error(exc):
                    continue
                return _Probe(host, reason=type(exc).__name__)
        return _Probe(host, reason="unreachable")  # pragma: no cover - the loop always returns
    finally:
        session.close()


def detect(summaries: list[ModemSummary], *, timeout: float = 3.0) -> list[Detection]:
    """Probe every distinct catalog ``default_host`` concurrently and return the hosts that answered."""
    hosts = _sweep_hosts(summaries)
    if not hosts:
        return []

    with ThreadPoolExecutor(max_workers=min(len(hosts), _MAX_WORKERS)) as pool:
        probes = list(pool.map(lambda host: _probe(host, timeout), hosts))

    # Logged here, not in the workers, so the capture context and the log order stay the caller's.
    detections: list[Detection] = []
    for probe in probes:
        log_event(_logger, DetectionProbeResult(host=probe.host, observation=probe.observation, reason=probe.reason))
        if probe.observation is None:
            continue
        match = match_page(probe.text, summaries)
        log_event(
            _logger,
            DetectionMatched(
                host=probe.host,
                models=[f"{s.manufacturer} {s.model}" for s in match.models],
                buckets=match.buckets,
                matched=match.matched,
            ),
        )
        detections.append(Detection(host=probe.host, observation=probe.observation, match=match))
    return detections
