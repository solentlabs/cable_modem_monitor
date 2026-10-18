"""Tests for detection.detect() — the credential-free sweep, against local test servers.

Each case stands up real HTTP(S) listeners on loopback; a summary's
``default_host`` carries the listener's ``127.0.0.1:port``. Contract:
DETECTION_SPEC.md § Sweep and § Bounds.
"""

from __future__ import annotations

import contextlib
import datetime
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import (
    Detection,
    Observation,
    _sweep_hosts,
    detect,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import LandingSignals
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    DetectionMatched,
    DetectionProbeResult,
)

from tests.orchestration.event_capture import assert_event_emitted, capture_events

LOOPBACK = "127.0.0.1"
TIMEOUT = 1.0


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:
    """Enable sockets for every test in this module."""


# ---------------------------------------------------------------------------
# Test servers
# ---------------------------------------------------------------------------


@dataclass
class Reply:
    """One canned response."""

    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    before: Callable[[], object] | None = None


@dataclass
class Site:
    """A loopback listener: routes in, requests seen out."""

    port: int
    routes: dict[str, Reply] = field(default_factory=dict)
    seen: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def host(self) -> str:
        return f"{LOOPBACK}:{self.port}"

    def requests_for(self, path: str) -> int:
        return sum(1 for seen_path, _ in self.seen if seen_path == path)


def _handler_for(site: Site) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            site.seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}))
            reply = site.routes.get(self.path, Reply(status=404))
            if reply.before:
                reply.before()
            self.send_response_only(reply.status)  # no automatic Server or Date header
            for name, value in reply.headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(reply.body)))
            self.end_headers()
            # The client stops reading at the body cap.
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(reply.body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    return Handler


@contextmanager
def serve(*, tls: Path | None = None) -> Iterator[Site]:
    """Run a listener on a free loopback port; ``tls`` is a directory holding cert.pem and key.pem."""
    site = Site(port=0)
    server = ThreadingHTTPServer((LOOPBACK, 0), _handler_for(site))
    site.port = server.server_address[1]
    if tls is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(tls / "cert.pem", tls / "key.pem")
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield site
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def tls_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A self-signed certificate: detection runs with verification off, as Core does everywhere."""
    directory = tmp_path_factory.mktemp("tls")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "detection-test")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    (directory / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return directory


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((LOOPBACK, 0))
        port: int = s.getsockname()[1]
    return port


def _summaries(*hosts: str, model: str = "AB600") -> list[ModemSummary]:
    """One catalog entry per host, all naming the same model."""
    return [ModemSummary(manufacturer="Acme", model=model, default_host=host) for host in hosts]


def _page(body: str = "<html><title>Acme AB600</title></html>") -> Reply:
    return Reply(headers={"Content-Type": "text/html"}, body=body.encode())


# ---------------------------------------------------------------------------
# Answering hosts
# ---------------------------------------------------------------------------


def test_answering_host_returns_observation_and_match() -> None:
    with serve() as site:
        site.routes["/"] = Reply(
            status=200,
            headers={"Content-Type": "text/html", "Server": "micro_httpd", "WWW-Authenticate": 'Basic realm="x"'},
            body=b"<html><head><title>\n  Acme   AB600 </title></head>"
            b'<body><input type="password" name="pw"></body></html>',
        )

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert len(result) == 1
    detection = result[0]
    assert detection.host == site.host
    assert detection.observation == Observation(
        scheme="http",
        status=200,
        final_path="/",
        server="micro_httpd",
        title="Acme AB600",
        www_authenticate='Basic realm="x"',
        password_field=True,
    )
    assert [s.model for s in detection.match.models] == ["AB600"]
    assert detection.match.buckets == ["Acme"]


def test_server_header_alone_can_match() -> None:
    with serve() as site:
        site.routes["/"] = Reply(headers={"Server": "Acme AB600"}, body=b"")

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert [s.model for s in result[0].match.models] == ["AB600"]
    assert result[0].observation.server == "Acme AB600"
    assert result[0].observation.title is None
    assert result[0].observation.password_field is False


def test_host_answering_with_no_hit_is_still_returned() -> None:
    with serve() as site:
        site.routes["/"] = _page("<html><title>Router</title></html>")

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert len(result) == 1
    assert result[0].match.models == []
    assert result[0].match.buckets == []
    assert result[0].observation.title == "Router"


@pytest.mark.parametrize(
    ("reply", "status", "www_authenticate"),
    [
        (Reply(status=401, headers={"WWW-Authenticate": "Basic"}, body=b"Acme AB600"), 401, "Basic"),
        (Reply(status=403, body=b"Acme AB600"), 403, None),
        (Reply(status=500, body=b"Acme AB600"), 500, None),
    ],
    ids=["401-challenge", "403", "500"],
)
def test_any_http_response_answers(reply: Reply, status: int, www_authenticate: str | None) -> None:
    """A refusal is still a device speaking; its page text is matched all the same."""
    with serve() as site:
        site.routes["/"] = reply

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert result[0].observation.status == status
    assert result[0].observation.www_authenticate == www_authenticate
    assert [s.model for s in result[0].match.models] == ["AB600"]


# ---------------------------------------------------------------------------
# Redirects and schemes
# ---------------------------------------------------------------------------


def test_redirect_chain_is_followed_to_the_final_path() -> None:
    with serve() as site:
        site.routes["/"] = Reply(status=302, headers={"Location": "/a"})
        site.routes["/a"] = Reply(status=301, headers={"Location": "/b?x=1"})
        site.routes["/b?x=1"] = _page()

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert result[0].observation.final_path == "/b"
    assert result[0].observation.status == 200
    assert [s.model for s in result[0].match.models] == ["AB600"]


def test_more_than_five_redirects_is_not_an_answer_and_is_not_retried() -> None:
    with serve() as site:
        for hop in range(8):
            site.routes["/" if hop == 0 else f"/{hop}"] = Reply(status=302, headers={"Location": f"/{hop + 1}"})

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert result == []
    assert site.requests_for("/") == 1


def test_five_redirects_is_within_the_limit() -> None:
    with serve() as site:
        for hop in range(5):
            site.routes["/" if hop == 0 else f"/{hop}"] = Reply(status=302, headers={"Location": f"/{hop + 1}"})
        site.routes["/5"] = _page()

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert result[0].observation.final_path == "/5"


@pytest.mark.filterwarnings("ignore::urllib3.exceptions.InsecureRequestWarning")
def test_a_tls_listener_answers_on_the_first_attempt(tls_dir: Path) -> None:
    """https is tried first (CONFIG_FLOW_SPEC § Step 4 prefers HTTPS); its answer wins and http is not tried."""
    with serve(tls=tls_dir) as site:
        site.routes["/"] = _page()

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert len(result) == 1
    assert result[0].observation.scheme == "https"
    assert [s.model for s in result[0].match.models] == ["AB600"]
    assert site.requests_for("/") == 1


@pytest.mark.filterwarnings("ignore::urllib3.exceptions.InsecureRequestWarning")
def test_redirect_may_cross_from_http_to_https(tls_dir: Path) -> None:
    with serve(tls=tls_dir) as secure, serve() as plain:
        secure.routes["/login"] = _page()
        plain.routes["/"] = Reply(status=302, headers={"Location": f"https://{secure.host}/login"})

        result = detect(_summaries(plain.host), timeout=TIMEOUT)

    assert result[0].host == plain.host
    assert result[0].observation.scheme == "https"
    assert result[0].observation.final_path == "/login"


def test_http_is_tried_when_https_yields_no_response() -> None:
    """A plain-http modem cannot answer a TLS handshake; the same host answers over http."""
    with serve() as site:
        site.routes["/"] = _page()

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert result[0].observation.scheme == "http"
    assert [s.model for s in result[0].match.models] == ["AB600"]


# ---------------------------------------------------------------------------
# Hosts that do not answer
# ---------------------------------------------------------------------------


def test_refused_host_is_not_an_answering_host() -> None:
    assert detect(_summaries(f"{LOOPBACK}:{_free_port()}"), timeout=TIMEOUT) == []


def test_timeout_is_not_an_answering_host() -> None:
    with serve() as site:
        gate = threading.Event()
        site.routes["/"] = Reply(body=b"Acme AB600", before=gate.wait)

        started = time.monotonic()
        try:
            result = detect(_summaries(site.host), timeout=0.2)
        finally:
            gate.set()  # release the stalled handler so the server can close
        elapsed = time.monotonic() - started

    assert result == []
    # http times out, https is tried once and fails the same way: bounded, never open-ended.
    assert elapsed < 1.0


def test_no_summaries_means_no_probes() -> None:
    assert detect([], timeout=TIMEOUT) == []


def test_unanswering_hosts_do_not_hide_an_answering_one() -> None:
    with serve() as site:
        site.routes["/"] = _page()

        result = detect(_summaries(f"{LOOPBACK}:{_free_port()}", site.host), timeout=TIMEOUT)

    assert [d.host for d in result] == [site.host]


# ---------------------------------------------------------------------------
# Body cap
# ---------------------------------------------------------------------------

BODY_CAP = 256 * 1024
FILLER = b"x " * (BODY_CAP // 2)

BODY_CAP_CASES = [
    (b"AB600 " + FILLER + FILLER, True, "name-first"),
    (FILLER + FILLER + b" AB600", False, "name-past-cap"),
]


@pytest.mark.parametrize(("body", "found", "case_id"), BODY_CAP_CASES, ids=[c[-1] for c in BODY_CAP_CASES])
def test_body_is_read_up_to_the_cap(body: bytes, found: bool, case_id: str) -> None:
    with serve() as site:
        site.routes["/"] = Reply(body=body)

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert bool(result[0].match.models) is found


# ---------------------------------------------------------------------------
# Sweep: ordering, concurrency, credentials
# ---------------------------------------------------------------------------

# ┌──────────────────────────────┬───────────────────────────┬────────────────────┐
# │ default_host per entry       │ sweep order               │ id                 │
# ├──────────────────────────────┼───────────────────────────┼────────────────────┤
# │ a, b, b, c, c, c             │ c, b, a                   │ most-frequent-first│
# │ b, a, c                      │ a, b, c                   │ ties-lexical       │
# │ a, a, b, b, c                │ a, b, c                   │ tie-then-lexical   │
# │ (none)                       │ (none)                    │ empty              │
# └──────────────────────────────┴───────────────────────────┴────────────────────┘
SWEEP_ORDER_CASES = [
    (["a", "b", "b", "c", "c", "c"], ["c", "b", "a"], "most-frequent-first"),
    (["b", "a", "c"], ["a", "b", "c"], "ties-lexical"),
    (["a", "a", "b", "b", "c"], ["a", "b", "c"], "tie-then-lexical"),
    ([], [], "empty"),
]


@pytest.mark.parametrize(("hosts", "expected", "case_id"), SWEEP_ORDER_CASES, ids=[c[-1] for c in SWEEP_ORDER_CASES])
def test_sweep_hosts_are_distinct_most_frequent_first_then_lexical(
    hosts: list[str], expected: list[str], case_id: str
) -> None:
    assert _sweep_hosts(_summaries(*hosts)) == expected


def test_detections_follow_sweep_order() -> None:
    with serve() as rare, serve() as common:
        rare.routes["/"] = _page()
        common.routes["/"] = _page()

        result = detect(_summaries(rare.host, common.host, common.host), timeout=TIMEOUT)

    assert [d.host for d in result] == [common.host, rare.host]


def test_hosts_are_probed_concurrently() -> None:
    """Every probe waits for all the others: a sequential sweep would time the barrier out."""
    count = 4
    barrier = threading.Barrier(count, timeout=5)

    def rendezvous() -> None:
        with contextlib.suppress(threading.BrokenBarrierError):
            barrier.wait()

    sites: list[Site] = []
    with _serve_many(count, sites):
        for site in sites:
            site.routes["/"] = Reply(body=b"Acme AB600", before=rendezvous)

        result = detect(_summaries(*(s.host for s in sites)), timeout=TIMEOUT * 3)

    assert len(result) == count
    assert not barrier.broken


@contextmanager
def _serve_many(count: int, into: list[Site]) -> Iterator[None]:
    with ExitStack() as stack:
        into.extend(stack.enter_context(serve()) for _ in range(count))
        yield


def test_probe_sends_one_get_and_no_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A netrc entry and a proxy in the environment must not reach a credential-free probe."""
    netrc = tmp_path / "netrc"
    netrc.write_text(f"machine {LOOPBACK} login admin password hunter2\n")
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("HTTP_PROXY", f"http://{LOOPBACK}:{_free_port()}")
    monkeypatch.setenv("HTTPS_PROXY", f"http://{LOOPBACK}:{_free_port()}")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    with serve() as site:
        site.routes["/"] = _page()

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    assert len(result) == 1
    assert len(site.seen) == 1
    path, headers = site.seen[0]
    assert path == "/"
    assert not {"authorization", "cookie", "proxy-authorization"} & headers.keys()


def test_error_status_is_not_retried() -> None:
    with serve() as site:
        site.routes["/"] = Reply(status=503, body=b"busy")

        detect(_summaries(site.host), timeout=TIMEOUT)

    assert site.requests_for("/") == 1


# ---------------------------------------------------------------------------
# Log events
# ---------------------------------------------------------------------------


def test_each_probed_host_logs_one_probe_result_and_each_answer_logs_its_match() -> None:
    dead = f"{LOOPBACK}:{_free_port()}"
    with serve() as site:
        site.routes["/"] = _page()

        with capture_events() as events:
            result = detect([*_summaries(dead, model="Other"), *_summaries(site.host)], timeout=TIMEOUT)

    assert isinstance(result[0], Detection)
    probes = [e for e in events if isinstance(e, DetectionProbeResult)]
    assert sorted(e.host for e in probes) == sorted([dead, site.host])
    assert_event_emitted(events, DetectionProbeResult, host=dead, observation=None)
    assert_event_emitted(events, DetectionProbeResult, host=site.host, reason=None)
    assert_event_emitted(
        events,
        DetectionMatched,
        host=site.host,
        models=["Acme AB600"],
        buckets=["Acme"],
        matched=["Acme", "AB600"],
    )
    assert len([e for e in events if isinstance(e, DetectionMatched)]) == 1


# ---------------------------------------------------------------------------
# Reply evidence and candidates
# ---------------------------------------------------------------------------


def test_reply_carries_paths_cookies_and_server_across_the_redirect_chain() -> None:
    with serve() as site:
        site.routes["/"] = Reply(status=302, headers={"Location": "/login.html", "Set-Cookie": "SID=1; Path=/"})
        site.routes["/login.html"] = Reply(
            headers={"Content-Type": "text/html", "Server": "lighttpd/1.4.67"},
            body=b'<script src="/js/app.js"></script><form action="/go.cgi">',
        )

        result = detect(_summaries(site.host), timeout=TIMEOUT)

    reply = result[0].reply
    assert reply.paths == ["/js/app.js", "/go.cgi"]
    assert reply.cookies == ["SID"]
    assert reply.server == "lighttpd"


def test_candidates_rank_the_entry_whose_config_signals_are_in_the_reply() -> None:
    with serve() as site:
        site.routes["/"] = Reply(
            headers={"Content-Type": "text/html"},
            body=b'<form action="/check.jst"><input type="text">',
        )
        catalog = [
            ModemSummary(manufacturer="Acme", model="Other", default_host=site.host),
            ModemSummary(
                manufacturer="Acme",
                model="Mine",
                default_host=site.host,
                landing_signals=LandingSignals(("/check.jst",)),
            ),
        ]

        with capture_events() as events:
            result = detect(catalog, timeout=TIMEOUT)

    assert [(c.summary.model, c.tier, c.signals) for c in result[0].candidates] == [
        ("Mine", 1, ["/check.jst"]),
        ("Other", 3, []),
    ]
    assert_event_emitted(events, DetectionMatched, host=site.host, signals=["/check.jst"], candidates=2)


def test_a_login_form_removes_a_no_auth_entry_from_the_candidates() -> None:
    with serve() as site:
        site.routes["/"] = Reply(headers={"Content-Type": "text/html"}, body=b'<input type="password" name="pw">')
        catalog = [
            ModemSummary(manufacturer="Acme", model="Open", default_host=site.host, auth_strategies=["none"]),
            ModemSummary(manufacturer="Acme", model="Closed", default_host=site.host, auth_strategies=["form"]),
        ]

        result = detect(catalog, timeout=TIMEOUT)

    assert [c.summary.model for c in result[0].candidates] == ["Closed"]


def test_schemes_are_tried_https_first_then_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """The order follows CONFIG_FLOW_SPEC § Step 4: a TLS answer is preferred; http only when https gets none."""
    import requests
    from solentlabs.cable_modem_monitor_core import detection

    urls: list[str] = []

    class Silent:
        trust_env = True
        max_redirects = 0

        def get(self, url: str, **_: object) -> object:
            urls.append(url)
            raise requests.exceptions.ConnectTimeout("no answer")

        def close(self) -> None:
            pass

    monkeypatch.setattr(detection, "create_session", Silent)

    assert detect(_summaries("192.0.2.1"), timeout=TIMEOUT) == []
    assert urls == ["https://192.0.2.1/", "http://192.0.2.1/"]
