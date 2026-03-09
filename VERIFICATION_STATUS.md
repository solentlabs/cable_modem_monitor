# Modem Parser Verification Status

## Parser Status Model

Parsers use a `ParserStatus` enum to track their verification state:

```python
from enum import StrEnum

class ParserStatus(StrEnum):
    IN_PROGRESS = "in_progress"                   # Actively being developed
    AWAITING_VERIFICATION = "awaiting_verification"  # Released, needs user confirmation
    VERIFIED = "verified"                         # Confirmed working by real user
    UNSUPPORTED = "unsupported"                   # Modem locked down, kept for documentation
```

### Status Definitions

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **IN_PROGRESS** | Parser actively being developed (feature branch/WIP PR) | Complete development |
| **AWAITING_VERIFICATION** | Parser released but awaiting first user confirmation | Needs community testing |
| **VERIFIED** | User with real modem confirmed parser works correctly | Stable for use |
| **UNSUPPORTED** | Modem locked down or no exposed status pages, kept for documentation | Awaiting user data |

### Using Status in Parsers

Status is declared in each modem's `modem.yaml` under `status_info.status`.
The `list-supported-modems.py` script reads these values to generate the
modem database.

## Current Status

### Tools

```bash
# Human-readable table
python scripts/dev/list-supported-modems.py

# JSON output
python scripts/dev/list-supported-modems.py --json

# Markdown table
python scripts/dev/list-supported-modems.py --markdown
```

---

**Maintainer:** @kwschulz
