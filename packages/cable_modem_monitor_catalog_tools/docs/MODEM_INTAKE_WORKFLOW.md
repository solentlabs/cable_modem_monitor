# Modem Intake Workflow

Onboard a new cable modem from a HAR capture to a tested catalog entry.
If the modem uses patterns Core already knows, onboarding is fully
automated. If the modem uses something new, the pipeline stops with
a clear report of what Core needs to support.

> **Authoritative spec:** [ONBOARDING_SPEC.md](../../cable_modem_monitor_core/docs/ONBOARDING_SPEC.md)
> covers tool contracts, decision trees, validation rules, worked examples,
> and error handling in full detail. This document is the operator workflow.

## Arguments

The user provides one of:

- A HAR file path (local)
- A GitHub issue number with an attached HAR
- A modem manufacturer + model name (looks up existing HAR in catalog)

## Pipeline Flow

```text
validate_har -> scan_fleet -> analyze_har(fleet) -> [check for gaps]
    -> enrich_metadata -> generate_config(fleet) -> generate_golden_file
    -> write_modem_package -> run_tests -> [fix failures] -> show changes
```

Two outcomes:

- **Clean pipeline (no gaps):** produces catalog files
- **Gaps detected:** reports what Core doesn't support and stops

## Step 1: Obtain HAR

If given a GitHub issue number:

```bash
gh issue view <number> --json body,comments
```

Extract HAR attachment URL, download to a temp directory.

If given a local path, use directly.

## Step 2: Validate HAR

```python
from solentlabs.cable_modem_monitor_catalog_tools.validate_har import validate_har
result = validate_har(har_path)
```

If `result.valid is False`: stop and report the issues to the user.
Validation catches structural problems and missing auth flows early
-- there is no point scanning the fleet or running analysis on a
bad HAR. Common fix: HAR was captured with an existing session
(post-auth). Ask user to recapture in incognito/private browsing.

## Step 3: Scan Fleet Patterns

```python
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_catalog_tools.fleet_scanner import scan_fleet

fleet = scan_fleet(CATALOG_PATH)
```

Fleet patterns augment Core's baseline detection with proven patterns
from existing modems (selector directions, system_info labels, aggregate
fields). Pass `fleet` to both `analyze_har` and `generate_config`.

## Step 4: Analyze HAR

```python
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har
result = analyze_har(har_path, fleet=fleet)
analysis = result.to_dict()
```

Check three outputs:

1. **`hard_stops`** -- if non-empty, report and stop
2. **`warnings`** -- note for later, don't stop
3. **`core_gaps`** -- if present, report and stop (Step 5)

Report what was detected:

- Transport: `{analysis["transport"]}`
- Auth: `{analysis["auth"]["strategy"]}` (confidence: `{analysis["auth"]["confidence"]}`)
- Actions: logout={yes/no}, restart={yes/no}
- Sections: list formats and channel counts

## Step 5: Check for Core Gaps

If `analysis["core_gaps"]` is present, the modem uses a pattern Core
doesn't support yet. **Stop config generation.** Report:

1. What was successfully detected (transport, session, etc.)
2. For each gap:
   - **Category**: what kind of pattern is missing
   - **Summary**: human-readable description
   - **Evidence**: wire data from the HAR
3. Suggest next steps:
   - `unmatched_login`: new login URL pattern needed in `auth_patterns.json`,
     or a new auth strategy needed in Core
   - `auth_unknown`: new auth strategy needed in Core
   - `unmatched_restart` / `unmatched_logout`: new action URL pattern needed
     in `action_patterns.json`

Format the report so it can be pasted into a GitHub issue for a
development effort. Do NOT try to resolve gaps by patching the
analysis dict.

If no gaps: proceed to Step 6.

## Step 6: Enrich Metadata

```python
from solentlabs.cable_modem_monitor_catalog_tools.enrich_metadata import enrich_metadata
enrich_result = enrich_metadata(analysis, existing_config=None, user_input=user_metadata)
metadata = enrich_result.metadata
```

For each item in `enrich_result.missing`:

- **hardware.chipset**: web search `"{manufacturer} {model} chipset"`
- **hardware.docsis_version**: check if OFDM channels detected (= 3.1), else 3.0
- **isps**: web search `"{model} compatible ISPs"`
- **default_host**: usually 192.168.100.1 for DOCSIS modems

Ask user to confirm or provide values you can't find.

## Step 7: Generate Config

```python
from solentlabs.cable_modem_monitor_catalog_tools.generate_config import generate_config
result = generate_config(analysis, metadata, fleet=fleet)
```

If `result.validation.valid is False`:

- Read the errors
- Fix the analysis dict or metadata
- Retry

Show the generated YAML to the user for review before proceeding.

## Step 8: Generate Golden File + Write Package

```python
from solentlabs.cable_modem_monitor_catalog_tools.generate_golden_file import generate_golden_file
golden = generate_golden_file(str(har_path), result.parser_yaml)
```

Report channel counts for sanity check:

- Downstream: N channels, fields: [list]
- Upstream: N channels, fields: [list]
- System info: [list of fields]

Then write the catalog package:

```python
from solentlabs.cable_modem_monitor_catalog_tools.write_modem_package import write_modem_package
write_result = write_modem_package(output_dir, ...)
```

## Step 9: Run Tests

```python
from solentlabs.cable_modem_monitor_core.test_harness.runner import run_tests
test_result = run_tests(modem_dir)
```

If tests fail, diagnose from the structured diff:

- **Auth failure**: check modem.yaml auth fields against HAR login flow
- **404 on resource**: check parser.yaml resource paths vs HAR URLs
- **Empty channels**: check column indices/field offsets
- **Golden mismatch**: compare field-by-field diff

Fix the config, re-run. Loop until green.

## Step 10: Show Changes

List all files created/modified. Show `git diff --stat`. Do NOT commit or
push -- the developer stages and commits per project rules.

## Key Rules

1. **HAR is the authority.** Every config decision traces to wire evidence.
   If the HAR doesn't show it, don't guess.
2. **Known patterns are automated.** If the pipeline can classify
   everything, config generation is deterministic. No LLM reasoning
   needed for the common case.
3. **Unknown patterns are Core gaps.** If the pipeline can't classify
   something, stop and report. Don't try to resolve it -- that's a
   development effort, not an intake task.
4. **Only the catalog changes.** Onboarding a new modem should only add
   files to `packages/cable_modem_monitor_catalog/`. If Core changes
   are needed, that's a gap to flag.
5. **Iterate on test failures.** Expect the first run to fail. Diagnose,
   fix, re-run. This is normal.
6. **Never commit automatically.** Show changes, let the developer stage.
7. **Alias vs separate entry.** Each model a user would purchase by name
   gets its own catalog directory. Aliases are only for manufacturer
   rebrands, internal/OEM model numbers, and marketing name variants.
   See `MODEM_YAML_SPEC.md` § Aliases vs Separate Entries.
8. **Consolidate issue resources.** When a HAR is incomplete (e.g.,
   missing XHR due to Playwright `networkidle` bug), extract data from
   screenshots, embedded HTML/JS, and user confirmations before building
   the fixture. Note provenance in `modem.yaml` sources.
