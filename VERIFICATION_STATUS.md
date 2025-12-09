# Modem Parser Verification Status

## Parser Status Model

Parsers use a `ParserStatus` enum to track their verification state:

```python
from enum import Enum

class ParserStatus(str, Enum):
    IN_PROGRESS = "in_progress"                   # Actively being developed
    AWAITING_VERIFICATION = "awaiting_verification"  # Released, needs user confirmation
    VERIFIED = "verified"                         # Confirmed working by real user
    BROKEN = "broken"                             # Known issues, needs fixes
    DEPRECATED = "deprecated"                     # Phased out, use alternative
```

### Status Definitions

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **IN_PROGRESS** | Parser actively being developed (feature branch/WIP PR) | Complete development |
| **AWAITING_VERIFICATION** | Parser released but awaiting first user confirmation | Needs community testing |
| **VERIFIED** | User with real modem confirmed parser works correctly | Stable for use |
| **BROKEN** | Known issues preventing normal operation | Fix required before use |
| **DEPRECATED** | Parser being phased out (model discontinued, merged elsewhere) | Migrate to replacement |

### Using Status in Parsers

```python
from ..base_parser import ModemCapability, ModemParser, ParserStatus

class ExampleParser(ModemParser):
    name = "Example CM1000"
    manufacturer = "Example"
    models = ["CM1000"]

    # Parser status
    status = ParserStatus.PENDING  # or VERIFIED, BROKEN, DEPRECATED
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/XX"
```

## Current Status

See **[tests/parsers/FIXTURES.md](tests/parsers/FIXTURES.md)** for the master modem database with current verification status.

### Tools

```bash
# Human-readable table
python scripts/dev/list-supported-modems.py

# JSON output
python scripts/dev/list-supported-modems.py --json

# Markdown table
python scripts/dev/list-supported-modems.py --markdown

# Regenerate fixture index
python scripts/generate_fixture_index.py
```

## Verification Sources

Each parser's `verification_source` field links to the GitHub issue, PR, or other evidence. Check individual parser files in `custom_components/cable_modem_monitor/parsers/`.

---

**Maintainer:** @kwschulz
