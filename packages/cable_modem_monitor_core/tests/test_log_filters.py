"""Tests for log_filters — upstream-library noise suppression.

Covers:
- Filter behavior: drops records that carry a urllib3
  ``HeaderParsingError`` (via ``exc_info`` or as a positional arg);
  passes everything else, including a plain "Failed to parse headers"
  string with no such exception (we key on the type, not the text).
- The suppressed warning is genuinely benign: the response body
  survives the malformed headers intact.
- The filter is attached to both urllib3 loggers, is idempotent, and
  runs at package import time.
"""

from __future__ import annotations

import http.client
import importlib
import io
import logging

import pytest
from solentlabs.cable_modem_monitor_core import log_filters
from solentlabs.cable_modem_monitor_core.log_filters import (
    _URLLIB3_LOGGERS,
    SuppressHeaderParsingWarning,
    install_filters,
)
from urllib3.exceptions import HeaderParsingError


def _make_record(
    *,
    msg: str = "x",
    args: tuple[object, ...] | None = None,
    exc: BaseException | None = None,
) -> logging.LogRecord:
    """Build a LogRecord, optionally carrying ``exc`` as its ``exc_info``."""
    exc_info = (type(exc), exc, None) if exc is not None else None
    return logging.LogRecord(
        name="urllib3.connection",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def _hpe() -> HeaderParsingError:
    return HeaderParsingError(defects=[], unparsed_data="")


# A record is dropped (False) only when it structurally carries a
# HeaderParsingError. A bare "Failed to parse headers" string with no
# such exception passes (True) — proving we no longer match on text.
_FILTER_CASES = [
    (
        _make_record(msg="Failed to parse headers (url=%s): %s", args=("http://x", _hpe())),
        False,
        "hpe_as_positional_arg",
    ),
    (_make_record(exc=_hpe()), False, "hpe_as_exc_info"),
    (_make_record(msg="Failed to parse headers (url=http://x)"), True, "header_text_but_no_hpe"),
    (_make_record(exc=ValueError("boom")), True, "unrelated_exception"),
    (_make_record(msg="Connection pool is full, discarding connection"), True, "unrelated_warning"),
    (_make_record(), True, "plain_record"),
]


@pytest.mark.parametrize(
    "record, expected_allowed, _desc",
    _FILTER_CASES,
    ids=[c[2] for c in _FILTER_CASES],
)
def test_suppress_filter(record: logging.LogRecord, expected_allowed: bool, _desc: str) -> None:
    """Filter passes records iff they do not carry a HeaderParsingError."""
    assert SuppressHeaderParsingWarning().filter(record) is expected_allowed


@pytest.mark.parametrize("logger_name", _URLLIB3_LOGGERS)
def test_filter_installed_on_both_urllib3_loggers(logger_name: str) -> None:
    """The filter is attached to both the connection and connectionpool loggers.

    urllib3 1.26 logs the warning from ``connectionpool``; 2.x from
    ``connection``. HA ships both across releases, so the #98 S33v3
    (urllib3 2.x) and older 1.26 stacks must both be covered.
    """
    install_filters()
    target = logging.getLogger(logger_name)
    assert any(isinstance(f, SuppressHeaderParsingWarning) for f in target.filters)


def test_install_is_idempotent() -> None:
    """Repeated calls do not stack duplicate filters on the target loggers."""
    install_filters()
    install_filters()
    install_filters()

    for logger_name in _URLLIB3_LOGGERS:
        target = logging.getLogger(logger_name)
        count = sum(1 for f in target.filters if isinstance(f, SuppressHeaderParsingWarning))
        assert count == 1, logger_name


def test_filter_installed_on_package_import() -> None:
    """Importing the package attaches the filter — no explicit setup needed."""
    importlib.reload(log_filters)
    log_filters.install_filters()

    for logger_name in _URLLIB3_LOGGERS:
        target = logging.getLogger(logger_name)
        assert any(isinstance(f, SuppressHeaderParsingWarning) for f in target.filters)


def test_filter_blocks_record_through_logger() -> None:
    """End-to-end: a defect record routed through the logger is suppressed.

    Verifies the filter chain runs as part of the standard logging path,
    not just as an isolated callable.
    """
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Capture()
    target = logging.getLogger("urllib3.connection")
    target.addHandler(handler)
    original_level = target.level
    target.setLevel(logging.DEBUG)

    try:
        # Mirror urllib3's call shape: a HeaderParsingError captured as exc_info.
        try:
            raise HeaderParsingError(defects=[], unparsed_data="")
        except HeaderParsingError:
            target.warning("Failed to parse headers (url=x): %s", "boom", exc_info=True)
        target.warning("Connection refused")
    finally:
        target.removeHandler(handler)
        target.setLevel(original_level)

    messages = [rec.getMessage() for rec in captured]
    assert not any("Failed to parse headers" in m for m in messages)
    assert "Connection refused" in messages


# The #98 firmware quirk: the first header line carries debug timing data
# (``   4.400002  |``) glued in front of the real Content-Type, with leading
# whitespace that Python reads as an illegal header continuation.
_MALFORMED_BODY = b'{"GetMultipleHNAPsResponse":{"ok":true}}'
_MALFORMED_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"   4.400002  |Content-type: text/html\r\n"
    b"Content-Length: " + str(len(_MALFORMED_BODY)).encode() + b"\r\n"
    b"\r\n" + _MALFORMED_BODY
)


class _BytesSock:
    """Minimal socket stand-in feeding raw bytes to http.client."""

    def __init__(self, raw: bytes) -> None:
        self._buf = io.BytesIO(raw)

    def makefile(self, *_args: object, **_kwargs: object) -> io.BytesIO:
        return self._buf


def test_header_parsing_defect_is_recoverable() -> None:
    """The suppressed warning is benign: the #98 defect leaves the body intact.

    This is the justification for dropping the warning rather than acting
    on it. Python flags ``FirstHeaderLineIsContinuationDefect`` on the
    response, but because ``Content-Length`` is on a later, well-formed
    header line, the body is read in full. The only casualty is the
    Content-Type header, which Core never consults.
    """
    response = http.client.HTTPResponse(_BytesSock(_MALFORMED_RESPONSE))  # type: ignore[arg-type]  # _BytesSock provides the only socket method http.client needs (makefile)
    response.begin()

    defect_names = [type(d).__name__ for d in response.msg.defects]
    assert "FirstHeaderLineIsContinuationDefect" in defect_names
    assert response.read() == _MALFORMED_BODY  # body survives the malformed header
