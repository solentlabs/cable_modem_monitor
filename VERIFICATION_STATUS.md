***REMOVED*** Modem Parser Verification Status

***REMOVED******REMOVED*** Parser Status Model

Parsers use a `ParserStatus` enum to track their verification state:

```python
from enum import Enum

class ParserStatus(str, Enum):
    IN_PROGRESS = "in_progress"                   ***REMOVED*** Actively being developed
    AWAITING_VERIFICATION = "awaiting_verification"  ***REMOVED*** Released, needs user confirmation
    VERIFIED = "verified"                         ***REMOVED*** Confirmed working by real user
    BROKEN = "broken"                             ***REMOVED*** Known issues, needs fixes
    DEPRECATED = "deprecated"                     ***REMOVED*** Phased out, use alternative
```

***REMOVED******REMOVED******REMOVED*** Status Definitions

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **IN_PROGRESS** | Parser actively being developed (feature branch/WIP PR) | Complete development |
| **AWAITING_VERIFICATION** | Parser released but awaiting first user confirmation | Needs community testing |
| **VERIFIED** | User with real modem confirmed parser works correctly | Stable for use |
| **BROKEN** | Known issues preventing normal operation | Fix required before use |
| **DEPRECATED** | Parser being phased out (model discontinued, merged elsewhere) | Migrate to replacement |

***REMOVED******REMOVED******REMOVED*** Using Status in Parsers

```python
from ..base_parser import ModemCapability, ModemParser, ParserStatus

class ExampleParser(ModemParser):
    name = "Example CM1000"
    manufacturer = "Example"
    models = ["CM1000"]

    ***REMOVED*** Parser status
    status = ParserStatus.PENDING  ***REMOVED*** or VERIFIED, BROKEN, DEPRECATED
    verification_source = "https://github.com/solentlabs/cable_modem_monitor/issues/XX"
```

***REMOVED******REMOVED*** Current Status

See **[tests/parsers/FIXTURES.md](tests/parsers/FIXTURES.md)** for the master modem database with current verification status.

***REMOVED******REMOVED******REMOVED*** Tools

```bash
***REMOVED*** Human-readable table
python scripts/dev/list-supported-modems.py

***REMOVED*** JSON output
python scripts/dev/list-supported-modems.py --json

***REMOVED*** Markdown table
python scripts/dev/list-supported-modems.py --markdown

***REMOVED*** Regenerate fixture index
python scripts/generate_fixture_index.py
```

***REMOVED******REMOVED*** Verification Sources

Each parser's `verification_source` field links to the GitHub issue, PR, or other evidence. Check individual parser files in `custom_components/cable_modem_monitor/parsers/`.

---

**Maintainer:** @kwschulz
