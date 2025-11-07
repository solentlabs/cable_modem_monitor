# Feature Request: Phase 4 - Data-Driven JSON Configs

**Status:** ⏸️ DEFERRED
**Priority:** Low (Build when needed)
**Effort:** 2-3 weeks
**Target Version:** v4.0.0-alpha

---

## Trigger Conditions

**DO NOT BUILD unless one of these occurs:**

1. **Parser count > 10** - Maintenance burden becomes significant
2. **Community requests JSON configs** - Multiple users ask for easier contribution
3. **Parser complexity increases** - Maintenance becomes painful with Python-only approach

**Current Status:** 6 parsers, Python works fine. **WAIT.**

---

## Summary

Replace Python-based parser implementations with JSON configuration files that are interpreted by a generic parser. This makes it easier for community members to add support for new modems without writing Python code.

## Problem It Solves

- **High barrier to entry** - Contributors must know Python
- **Maintenance burden** - Each parser requires code review, testing, maintenance
- **Slow iteration** - Adding a modem requires full development cycle
- **Inconsistent quality** - Different parsers have different standards
- **Testing complexity** - Each parser needs its own test suite

## Proposed Solution

### JSON Parser Configuration Format

```json
{
  "parser": {
    "name": "Motorola MB8611",
    "manufacturer": "Motorola",
    "models": ["MB8611", "MB8612"],
    "priority": 100,
    "protocol": "hnap"
  },
  "authentication": {
    "strategy": "hnap_session",
    "login_url": "/Login.html",
    "hnap_endpoint": "/HNAP1/",
    "session_timeout_indicator": "UN-AUTH"
  },
  "url_patterns": [
    {
      "path": "/HNAP1/",
      "auth_method": "hnap",
      "auth_required": true
    }
  ],
  "detection": {
    "heuristics": [
      {
        "type": "html_contains",
        "value": "MB8611"
      },
      {
        "type": "hnap_action",
        "value": "GetMotoStatusConnectionInfo"
      }
    ]
  },
  "data_extraction": {
    "protocol": "hnap",
    "actions": [
      "GetMotoStatusStartupSequence",
      "GetMotoStatusConnectionInfo",
      "GetMotoStatusDownstreamChannelInfo",
      "GetMotoStatusUpstreamChannelInfo"
    ],
    "downstream_channels": {
      "source": "GetMotoStatusDownstreamChannelInfo.MotoConnDownstreamChannel",
      "format": "caret_delimited",
      "fields": [
        {"name": "channel_id", "index": 0, "type": "int"},
        {"name": "lock_status", "index": 1, "type": "string"},
        {"name": "modulation", "index": 2, "type": "string"},
        {"name": "ch_id", "index": 3, "type": "int"},
        {"name": "frequency", "index": 4, "type": "float", "unit": "MHz", "convert_to": "Hz"},
        {"name": "power", "index": 5, "type": "float"},
        {"name": "snr", "index": 6, "type": "float"},
        {"name": "corrected", "index": 7, "type": "int"},
        {"name": "uncorrected", "index": 8, "type": "int"}
      ],
      "delimiter": "^",
      "record_separator": "|+|"
    },
    "upstream_channels": {
      "source": "GetMotoStatusUpstreamChannelInfo.MotoConnUpstreamChannel",
      "format": "caret_delimited",
      "fields": [
        {"name": "channel_id", "index": 0, "type": "int"},
        {"name": "lock_status", "index": 1, "type": "string"},
        {"name": "modulation", "index": 2, "type": "string"},
        {"name": "ch_id", "index": 3, "type": "int"},
        {"name": "symbol_rate", "index": 4, "type": "int"},
        {"name": "frequency", "index": 5, "type": "float", "unit": "MHz", "convert_to": "Hz"},
        {"name": "power", "index": 6, "type": "float"}
      ],
      "delimiter": "^",
      "record_separator": "|+|"
    },
    "system_info": {
      "fields": [
        {
          "name": "system_uptime",
          "source": "GetMotoStatusConnectionInfo.MotoConnSystemUpTime",
          "type": "string"
        },
        {
          "name": "network_access",
          "source": "GetMotoStatusConnectionInfo.MotoConnNetworkAccess",
          "type": "string"
        }
      ]
    }
  },
  "extra_attributes": {
    "enabled": true,
    "fields": [
      {
        "name": "boot_status",
        "source": "GetMotoStatusStartupSequence.MotoConnBootStatus",
        "type": "string",
        "description": "Boot sequence status"
      },
      {
        "name": "security_status",
        "source": "GetMotoStatusStartupSequence.MotoConnSecurityStatus",
        "type": "string",
        "description": "Security encryption status"
      }
    ]
  }
}
```

### Generic Parser Implementation

Create a `GenericJSONParser` class that:
1. Reads JSON configuration
2. Executes defined data extraction logic
3. Handles multiple protocols (HTML, HNAP, future REST APIs)
4. Validates extracted data
5. Returns standardized format

## Technical Implementation

### Components

1. **JSON Schema** (`schema/parser_config.json`)
   - Defines structure and validation rules
   - Enforces required fields
   - Provides defaults

2. **Generic Parser** (`parsers/generic_json_parser.py`)
   - Interprets JSON configs
   - Supports multiple protocols (HTML, HNAP, SOAP, REST)
   - Field mapping and type conversion
   - Error handling

3. **Validation Tool** (`tools/validate_parser_config.py`)
   - CLI tool to validate JSON configs
   - Checks syntax, schema compliance, logic errors
   - Pre-commit hook integration

4. **Config Registry** (`parsers/json_configs/`)
   - Directory of JSON parser configs
   - Auto-discovery by integration
   - Version-controlled

### Example HTML Parser JSON

```json
{
  "parser": {
    "name": "Technicolor TC4400",
    "manufacturer": "Technicolor",
    "models": ["TC4400"],
    "priority": 100,
    "protocol": "html"
  },
  "authentication": {
    "strategy": "basic_http"
  },
  "url_patterns": [
    {"path": "/cmconnectionstatus.html", "auth_method": "basic"}
  ],
  "detection": {
    "heuristics": [
      {"type": "url_contains", "value": "cmconnectionstatus.html"},
      {"type": "html_contains", "value": "Board ID:"}
    ]
  },
  "data_extraction": {
    "protocol": "html",
    "downstream_channels": {
      "selector": "table th:contains('Downstream Channel Status')",
      "selector_type": "css",
      "table": {
        "header_row": 0,
        "data_start_row": 2,
        "columns": [
          {"name": "channel_id", "index": 1, "type": "int"},
          {"name": "lock_status", "index": 2, "type": "string"},
          {"name": "frequency", "index": 5, "type": "frequency"},
          {"name": "power", "index": 8, "type": "float"},
          {"name": "snr", "index": 7, "type": "float"},
          {"name": "corrected", "index": 11, "type": "int"},
          {"name": "uncorrected", "index": 12, "type": "int"}
        ]
      }
    }
  }
}
```

## Benefits

1. **Lower Barrier to Entry**
   - Community members can add modems by editing JSON
   - No Python knowledge required
   - Faster contribution cycle

2. **Consistency**
   - All parsers follow same structure
   - Enforced by JSON schema
   - Predictable behavior

3. **Easier Testing**
   - Generic parser tested once
   - JSON configs validated automatically
   - Reduced test complexity

4. **Dynamic Updates**
   - Parsers can be added/updated without code changes
   - Hot-reload capability (future)
   - Community contributions via PR to JSON files only

5. **Maintainability**
   - Single generic parser to maintain
   - JSON configs are declarative
   - Clear separation of concerns

6. **Extensibility**
   - Easy to add new protocols
   - Extra attributes defined in JSON
   - Future-proof architecture

## Challenges

1. **Complexity** - Generic parser must handle all edge cases
2. **Performance** - JSON parsing overhead (likely negligible)
3. **Debugging** - Errors in JSON configs may be harder to debug than Python
4. **Feature Parity** - Must support all current parser features
5. **Migration** - Converting existing parsers to JSON format

## Migration Strategy

1. **Phase 4a:** Implement JSON schema + generic parser
2. **Phase 4b:** Convert 2-3 parsers to JSON as pilots
3. **Phase 4c:** Validate performance and completeness
4. **Phase 4d:** Convert remaining parsers
5. **Phase 4e:** Deprecate Python-only parser approach

## Community Workflow

1. User requests modem support
2. They provide HTML samples or network captures
3. Maintainer (or user!) creates JSON config
4. Validation tool checks JSON
5. Submit PR with just the JSON file
6. Automated tests validate against fixtures
7. Merge and release

## Files to Create

- `custom_components/cable_modem_monitor/schema/parser_config.json`
- `custom_components/cable_modem_monitor/parsers/generic_json_parser.py`
- `custom_components/cable_modem_monitor/parsers/json_configs/`
- `tools/validate_parser_config.py`
- `docs/CONTRIBUTING_PARSERS.md`

## Success Criteria

- [ ] JSON schema supports all current parser features
- [ ] Generic parser can interpret JSON and extract data
- [ ] At least 3 existing parsers converted to JSON
- [ ] Validation tool catches common errors
- [ ] Community member successfully adds parser via JSON (without Python)
- [ ] Performance is acceptable (< 10% overhead vs Python)

## Alternative Considered: Python with Simplified API

Instead of JSON, provide a simplified Python DSL:

```python
parser = ParserBuilder("Motorola MB8611") \
    .manufacturer("Motorola") \
    .models(["MB8611", "MB8612"]) \
    .hnap_auth(endpoint="/HNAP1/") \
    .extract_downstream(
        source="GetMotoStatusDownstreamChannelInfo",
        format="caret_delimited",
        fields=["channel_id", "lock_status", "frequency", ...]
    ) \
    .build()
```

**Pros:** More flexible than JSON, still Python
**Cons:** Still requires Python knowledge, not as declarative

---

## Related Issues

- Architecture Roadmap Phase 4
- Community contribution requests
- Parser maintenance burden discussions

---

**Vote with 👍 if you want this feature!**
**Comment if you have parser config needs beyond current capabilities!**
