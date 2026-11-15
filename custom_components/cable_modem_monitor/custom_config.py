"""Custom config setup — run a modem.yaml the user edits and report what the attempt did.

The user edits the variant's modem.yaml in the setup dialog and retries;
each failed attempt logs one report built from the records it emitted. A
successful entry keeps the user's text and returns to the catalog file
when the catalog catches up.

See CONFIG_FLOW_SPEC.md § Custom Config Setup.
"""

from __future__ import annotations

import difflib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Literal

import yaml
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.config_loader import validate_modem_config
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig

from .core.log_buffer import sanitize_log_message, strip_logger_prefix

# The loggers an attempt's report reads: Core and this integration.
_CAPTURED_LOGGERS = (
    "solentlabs.cable_modem_monitor_core",
    "custom_components.cable_modem_monitor",
)

CatalogSync = Literal["adopt", "repair", "keep"]


class CustomYamlError(ValueError):
    """The edited text is not YAML, or does not match the modem.yaml schema."""


def parse_modem_yaml(text: str) -> ModemConfig:
    """Parse and schema-validate the user's modem.yaml text."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CustomYamlError(f"YAML syntax error: {exc}") from exc
    if not isinstance(data, dict):
        raise CustomYamlError("modem.yaml must be a mapping at the top level")
    try:
        return validate_modem_config(data)
    except ValidationError as exc:
        raise CustomYamlError(f"modem.yaml schema error: {exc}") from exc


def _parsed(text: str) -> Any:
    """Parsed YAML, or a sentinel that equals nothing when the text does not parse."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return object()


def same_config(a: str, b: str) -> bool:
    """Whether two modem.yaml texts parse to the same data (comments, formatting and key order ignored)."""
    return bool(_parsed(a) == _parsed(b))


def catalog_sync_action(*, catalog_text: str, user_text: str, base_text: str) -> CatalogSync:
    """What a custom entry does with the installed catalog file (CONFIG_FLOW_SPEC.md § Custom Config Setup)."""
    # Parsed comparison: comments, formatting and key order don't count.
    catalog = _parsed(catalog_text)
    if catalog == _parsed(user_text):
        return "adopt"
    if catalog != _parsed(base_text):
        return "repair"
    return "keep"


def yaml_diff(*, base_text: str, user_text: str, label: str) -> str:
    """Unified diff from the catalog text the user started from to the text in use."""
    return "".join(
        difflib.unified_diff(
            base_text.splitlines(keepends=True),
            user_text.splitlines(keepends=True),
            fromfile=f"catalog/{label}",
            tofile=f"custom/{label}",
        )
    )


class _AttemptHandler(logging.Handler):
    """Collects the attempt thread's records and passes on only what HA would have logged anyway."""

    def __init__(self, records: list[logging.LogRecord], thread_id: int, thresholds: dict[str, int]) -> None:
        """Collect ``thread_id``'s records; forward any record at or above its package's prior level."""
        super().__init__(logging.DEBUG)
        self._records = records
        self._thread_id = thread_id
        self._thresholds = thresholds

    def emit(self, record: logging.LogRecord) -> None:
        """Keep the attempt's records; hand HA's handlers only what they would have received."""
        if record.thread == self._thread_id:
            self._records.append(record)
        for name, threshold in self._thresholds.items():
            if record.name == name or record.name.startswith(f"{name}."):
                parent = logging.getLogger(name).parent
                if record.levelno >= threshold and parent is not None:
                    parent.handle(record)
                return


# One capture at a time: two would each detach the loggers from HA's
# handlers and restore each other's settings out of order.
_CAPTURE_LOCK = threading.Lock()


@contextmanager
def capture_attempt() -> Iterator[list[logging.LogRecord]]:
    """Capture every Core and integration record the calling thread emits, DEBUG and above."""
    # The loggers drop to DEBUG so the report holds every step whatever level
    # HA logs at. They stop propagating meanwhile, and the handler forwards
    # only records at or above the prior level, so HA's log gets nothing the
    # attempt added: those lines are unscrubbed, and only the report is.
    with _CAPTURE_LOCK:
        records: list[logging.LogRecord] = []
        loggers = [logging.getLogger(name) for name in _CAPTURED_LOGGERS]
        saved = [(lg.level, lg.propagate) for lg in loggers]
        thresholds = {lg.name: lg.getEffectiveLevel() for lg in loggers}
        handler = _AttemptHandler(records, threading.get_ident(), thresholds)
        for lg in loggers:
            lg.setLevel(logging.DEBUG)
            lg.propagate = False
            lg.addHandler(handler)
        try:
            yield records
        finally:
            for lg, (level, propagate) in zip(loggers, saved, strict=True):
                lg.removeHandler(handler)
                lg.setLevel(level)
                lg.propagate = propagate


def build_report(
    *,
    version: str,
    catalog_file: str,
    host: str,
    outcome: str,
    records: list[logging.LogRecord],
    scrub: Callable[[str], str],
) -> str:
    """The failed attempt's report, logged as one record; scrubbed and sanitized for public pasting."""
    lines = [
        "Cable Modem Monitor custom config report",
        f"integration: {version}",
        f"catalog file: {catalog_file}",
        f"host: {host}",
        f"outcome: {outcome}",
        "log:",
    ]
    for record in records:
        stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
        message = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            message = f"{message} ({type(record.exc_info[1]).__name__}: {record.exc_info[1]})"
        lines.append(f"{stamp} {record.levelname} {strip_logger_prefix(record.name)}: {message}")
    return sanitize_log_message(scrub("\n".join(lines)))
