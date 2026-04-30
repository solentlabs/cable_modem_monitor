"""Per-modem PostProcessor loader.

Some modems ship an optional ``parser.py`` alongside their
``parser.yaml`` to express transformations the declarative YAML
cannot — computed fields, cross-column derivations, unit
conversions. The convention: each ``parser.py`` defines a class
named ``PostProcessor`` whose methods (``parse_downstream``,
``parse_upstream``, etc.) are invoked by the parsing pipeline
after YAML-driven extraction completes.

This module is the runtime extension point that turns "this modem
ships a parser.py" into "the pipeline can call its hooks." It is a
peer of ``config_loader.load_parser_config`` — both load per-modem
artifacts during HA setup — and is consumed by both the runtime
HA adapter (``custom_components/cable_modem_monitor``) and the
test pipeline runner (``test_harness/runner.py``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

# Fixed class name for parser.py post-processors.
_POST_PROCESSOR_CLASS = "PostProcessor"


def load_post_processor(parser_py_path: Path) -> Any:
    """Dynamically import a PostProcessor from a parser.py file.

    Loads the module from *parser_py_path* and returns an instance
    of the ``PostProcessor`` class. The class name is a fixed
    convention — all parser.py files use ``PostProcessor``.

    Args:
        parser_py_path: Absolute path to the ``parser.py`` file.

    Returns:
        An instance of ``PostProcessor``, or ``None`` if the class
        is not defined in the module.
    """
    spec = importlib.util.spec_from_file_location(
        f"parser_py_{parser_py_path.parent.name}",
        parser_py_path,
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = getattr(module, _POST_PROCESSOR_CLASS, None)
    if cls is None:
        return None

    return cls()
