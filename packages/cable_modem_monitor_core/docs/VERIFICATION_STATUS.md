# Modem Parser Verification Status

## Parser Status Model

Parsers use a `ParserStatus` enum to track their verification state:

```python
from enum import StrEnum

class ParserStatus(StrEnum):
    AWAITING_VERIFICATION = "awaiting_verification"  # Released, needs user confirmation
    CONFIRMED = "confirmed"                          # Confirmed working by real user
    UNSUPPORTED = "unsupported"                      # Modem locked down, kept for documentation
```

### Status Definitions

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **AWAITING_VERIFICATION** | Parser released but awaiting first user confirmation | Needs community testing |
| **CONFIRMED** | User with real modem confirmed parser works correctly | Stable for use |
| **UNSUPPORTED** | Modem locked down or no exposed status pages, kept for documentation | Awaiting user data |

### Using Status in Parsers

Status is declared under `status` in each modem's variant file (`modem.yaml`
or `modem-{variant}.yaml`). For multi-variant modems, each variant carries its
own status independently — one variant can be `confirmed` while another is
`awaiting_verification`. Promotion from `awaiting_verification` to `confirmed`
follows the ingest procedure in
[MODEM_DIRECTORY_SPEC.md](MODEM_DIRECTORY_SPEC.md#verification-artifact).

---

**Maintainer:** @kwschulz
