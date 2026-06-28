"""Suppress upstream-library log noise that obscures CMM signal.

Some library WARNING records emit full tracebacks for conditions that
are not actionable for CMM contributors debugging modem behavior — they
look like unhandled exceptions but are caught internally by the
library that emitted them. Each filter below drops one specific known
pattern.

Filters are installed automatically when the ``cable_modem_monitor_core``
package is imported (see ``__init__.py``), so any consumer — HA
adapter, test harness, catalog tools, ad-hoc scripts — gets the same
clean log surface without explicit setup.

Adding a new filter:

1. Identify the logger name and a stable structural key on the record
   (an exception type beats a message substring — it survives wording
   changes and won't match unrelated text).
2. Add a ``Filter`` subclass below with a docstring explaining the
   source — which modem firmware, which library version, what
   triggers it, why it is harmless.
3. Register it in :func:`install_filters`.

Filters here are pure suppression. If a future case needs translation
("emit a single CMM-level note instead of dropping silently"), extend
the filter to log its own DEBUG-level record before returning False.
"""

from __future__ import annotations

import logging

from urllib3.exceptions import HeaderParsingError

# urllib3 moved the header-parse warning between versions: 1.26 emits it
# from ``urllib3.connectionpool``, 2.x from ``urllib3.connection``. HA
# ships different urllib3 versions across releases, so we attach to both.
_URLLIB3_LOGGERS = ("urllib3.connection", "urllib3.connectionpool")


def _carries_header_parsing_error(record: logging.LogRecord) -> bool:
    """True if the record is urllib3's recovered ``HeaderParsingError`` warning.

    urllib3 logs ``log.warning("Failed to parse headers ...: %s", url, hpe,
    exc_info=True)``. The ``HeaderParsingError`` reaches us structurally
    two ways depending on version (as the captured ``exc_info`` and as a
    positional arg); checking both means a wording or format change in
    urllib3 cannot silently re-open the noise.
    """
    exc_info = record.exc_info
    if exc_info and exc_info[0] is not None and issubclass(exc_info[0], HeaderParsingError):
        return True
    if record.args:
        return any(isinstance(arg, HeaderParsingError) for arg in record.args)
    return False


class SuppressHeaderParsingWarning(logging.Filter):
    """Drop urllib3's recovered ``HeaderParsingError`` warnings.

    Source: several modems return HTTP responses Python's header parser
    flags as malformed — ARRIS HNAP firmware prepends debug timing data
    to the first header line (``FirstHeaderLineIsContinuationDefect``,
    issue #98), the SB6141 puts a space before the colon
    (``MissingHeaderBodySeparatorDefect``). In every case urllib3 calls
    ``assert_header_parsing``, raises ``HeaderParsingError``, catches it
    internally, emits a WARNING with a full traceback, then returns the
    response anyway. The body parses fine (verified in
    ``test_header_parsing_defect_is_recoverable``), so the warning is
    per-poll noise.

    We key on the ``HeaderParsingError`` exception type carried on the
    record, not on the rendered message text. Every header-parse defect
    inherits from it, so one structural check covers all of them with no
    per-defect string registry, and it never matches an unrelated "parse
    headers" message. urllib3 only emits this on the recovered-internally
    path, so suppressing it cannot hide a real failure; genuine header
    corruption that loses data surfaces in Core's own logging (zero
    channels / parse error) instead.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not _carries_header_parsing_error(record)


def install_filters() -> None:
    """Install all CMM logging filters. Idempotent — safe to call repeatedly.

    Filters are attached to the loggers they target. Each filter type
    is added at most once per logger; subsequent calls re-check
    presence so reloading the package (or calling explicitly from a
    test fixture) does not stack duplicate filters.
    """
    for logger_name in _URLLIB3_LOGGERS:
        _ensure_filter(logger_name, SuppressHeaderParsingWarning)


def _ensure_filter(
    logger_name: str,
    filter_cls: type[logging.Filter],
) -> None:
    """Attach ``filter_cls`` to the named logger if not already present."""
    target = logging.getLogger(logger_name)
    for existing in target.filters:
        if isinstance(existing, filter_cls):
            return
    target.addFilter(filter_cls())
