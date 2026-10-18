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
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

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
# DETECTION_SPEC.md § Reply evidence: attribute values that point at a path.
_POINTER = re.compile(r"""\b(?:src|href|action|data)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.IGNORECASE)
_META = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_META_REFRESH = re.compile(r"http-equiv\s*=\s*[\"']?refresh\b", re.IGNORECASE)
_META_TARGET = re.compile(r"\burl\s*=\s*([^\s\"'>;]+)", re.IGNORECASE)


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
class Reply:
    """What a landing reply points at and sets: paths, cookie names and the ``Server`` product."""

    paths: list[str]
    cookies: list[str]
    server: str | None


@dataclass(frozen=True)
class Candidate:
    """A catalog entry the device could be, its tier and the config signals found in the reply."""

    summary: ModemSummary
    tier: int
    signals: list[str] = field(default_factory=list)
    named: bool = False


@dataclass(frozen=True)
class Detection:
    """One answering address with what it showed and the entries it could be, best first."""

    host: str
    observation: Observation
    match: PageMatch
    reply: Reply
    candidates: list[Candidate]


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
# Reply evidence
# ---------------------------------------------------------------------------


def _pointers(body: str) -> list[str]:
    """Attribute values and meta-refresh targets in ``body``, in page order."""
    found: list[tuple[int, str]] = []
    for m in _POINTER.finditer(body):
        found.append((m.start(), m.group(1) or m.group(2) or m.group(3) or ""))
    for m in _META.finditer(body):
        tag = m.group()
        target = _META_TARGET.search(tag)
        if _META_REFRESH.search(tag) and target:
            found.append((m.start(), target.group(1)))
    return [value for _, value in sorted(found)]


def _path_of(value: str, base_url: str) -> str | None:
    """The same-host path ``value`` points at, resolved against ``base_url``; None when it is not one."""
    value = value.strip()
    if not value or value.startswith("#"):
        return None  # the page itself
    resolved = urlparse(urljoin(base_url, value))
    if resolved.scheme not in ("http", "https") or resolved.hostname != urlparse(base_url).hostname:
        return None
    return resolved.path if resolved.path not in ("", "/") else None


def read_reply(hops: Sequence[tuple[str, Mapping[str, str], bytes]], cookies: Iterable[str] = ()) -> Reply:
    """Reduce a landing reply (each response of the redirect chain) to paths, cookie names and the Server product."""
    paths: list[str] = []
    for url, headers, body in hops:
        content_type = {name.lower(): value for name, value in headers.items()}.get("content-type")
        if content_type and "html" not in content_type.lower():
            continue
        for value in _pointers(body[:_BODY_CAP].decode("utf-8", errors="replace")):
            path = _path_of(value, url)
            if path and path not in paths:
                paths.append(path)

    server = None
    if hops:
        raw = {name.lower(): value for name, value in hops[-1][1].items()}.get("server")
        server = raw.split("/", 1)[0].strip() or None if raw else None
    return Reply(paths=paths, cookies=list(dict.fromkeys(cookies)), server=server)


# ---------------------------------------------------------------------------
# Narrowing
# ---------------------------------------------------------------------------


def _contradicted(entry: ModemSummary, observation: Observation) -> bool:
    """A login form contradicts an entry every variant of which needs no login."""
    return observation.password_field and bool(entry.auth_strategies) and set(entry.auth_strategies) == {"none"}


def narrow(summaries: list[ModemSummary], match: PageMatch, reply: Reply, observation: Observation) -> list[Candidate]:
    """Rank the catalog by what the reply shows (tier 1, 2, 3); a login form removes the no-auth entries."""
    named = {id(s) for s in match.models}
    makers = {name.lower() for name in match.buckets}
    ranked: list[Candidate] = []
    for entry in summaries:
        signals = [p for p in entry.landing_signals.paths if p in reply.paths]
        signals += [c for c in entry.landing_signals.cookies if c in reply.cookies]
        if id(entry) in named or signals:
            tier = 1
        elif _contradicted(entry, observation):
            continue
        elif any(name.lower() in makers for name in (entry.manufacturer, *entry.brands)) or (
            reply.server and reply.server.lower() in {s.lower() for s in entry.server_headers}
        ):
            tier = 2
        else:
            tier = 3
        ranked.append(Candidate(entry, tier, signals, named=id(entry) in named))
    # Stable: catalog order within a group. A named model outranks a shared signal.
    return sorted(ranked, key=lambda c: (c.tier, not c.named))


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
    reply: Reply | None = None
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
    """Send one credential-free ``GET /``: https first, http when https yields no HTTP response."""
    session = create_session()
    # Environment netrc and proxies would add credentials or reroute a LAN probe.
    session.trust_env = False
    session.max_redirects = _MAX_REDIRECTS
    try:
        for scheme in ("https", "http"):
            try:
                with session.get(f"{scheme}://{host}/", timeout=timeout, stream=True) as response:
                    body = _read_capped(response, time.monotonic() + timeout)
                    observation, text = describe_response(response.url, response.status_code, response.headers, body)
                    # Redirect hops were read when requests followed them; only the final body was capped.
                    hops = [(r.url, r.headers, r.content) for r in response.history]
                    hops.append((response.url, response.headers, body))
                    reply = read_reply(hops, [cookie.name for cookie in session.cookies])
                    return _Probe(host, observation, text, reply)
            except requests.RequestException as exc:
                # No HTTP response at all: the only case the other scheme can answer.
                # A refusal, an error status or a redirect loop is an answer or a verdict.
                if scheme == "https" and is_connectivity_error(exc):
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
        assert probe.reply is not None  # an observation always comes with its reply
        match = match_page(probe.text, summaries)
        candidates = narrow(summaries, match, probe.reply, probe.observation)
        log_event(
            _logger,
            DetectionMatched(
                host=probe.host,
                models=[f"{s.manufacturer} {s.model}" for s in match.models],
                buckets=match.buckets,
                matched=match.matched,
                signals=[signal for c in candidates for signal in c.signals],
                candidates=len(candidates),
            ),
        )
        detections.append(
            Detection(
                host=probe.host,
                observation=probe.observation,
                match=match,
                reply=probe.reply,
                candidates=candidates,
            )
        )
    return detections
