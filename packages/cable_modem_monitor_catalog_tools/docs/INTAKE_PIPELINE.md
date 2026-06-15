# Modem Intake Pipeline

How new modems go from a HAR capture to a tested catalog entry.

> **Authoritative spec:** [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md)
> covers tool contracts, decision trees, validation rules, worked examples,
> and error handling in full detail. This document is an overview.

---

## Who Does What

| Role | What they do |
| ------ | ------------- |
| **HA user filing a request** | Captures a HAR with [har-capture](https://github.com/solentlabs/har-capture) and submits it via [modem request issue](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml). |
| **Catalog contributor** | Runs the intake pipeline on their own HAR or on a submitted one, produces a draft catalog entry, opens a PR. AI assistance (e.g., [Claude Code](https://claude.com/claude-code)) is the expected helper for the judgment steps. See [MODEM_INTAKE_WORKFLOW.md](MODEM_INTAKE_WORKFLOW.md). |
| **Maintainer** | Reviews and merges PRs, develops Core when a CoreGap is reported, ships releases. |
| **MCP tools** | Orchestration accelerator for runs driven through an AI agent. Handle deterministic steps — HAR parsing, pattern matching, config generation, validation, test execution. |
| **LLM** | Handles judgment calls — ambiguous HTML formats, metadata web search, test failure diagnosis. |

The pipeline tooling is plain Python, but the judgment layer realistically benefits from AI assistance. This project itself was built with Claude Code; that's the assumed contributor path. Manual config creation also works — the specs are the authority — but expect it to take more iteration.

---

## Pipeline Overview

```text
HAR file
    │
    ▼
validate_har ─── structural + auth flow checks
    │
    │             catalog/modems/
    │                  │
    ▼                  ▼
    │             scan_fleet ─── build FleetPatterns from proven configs
    │                  │
    ▼                  │
analyze_har(fleet) ◄───┘ transport, auth, session, actions, format, fields
    │
    ├── hard_stops? → stop, report to user
    ├── core_gaps? → stop, report what Core needs (see below)
    │
    ▼
enrich_metadata ─ infer defaults, detect missing fields
    │
    ├── missing fields? → LLM web search (chipset, DOCSIS version, ISPs)
    │
    ▼
generate_config(fleet) ─ modem.yaml + parser.yaml (Pydantic-validated)
    │
    ├── validation errors? → LLM fixes, retries
    │
    ▼
generate_golden_file ─ parse HAR through generated config
    │
    ▼
write_modem_package ── place all files in catalog directory
    │
    ▼
run_tests ─────── HAR replay → auth → load → parse → golden file diff
    │
    ├── failures? → LLM diagnoses, fixes config, re-runs
    │
    ▼
catalog entry ready for review
```

**Two outcomes:**

- **Known patterns:** Pipeline runs end-to-end, produces a tested catalog entry.
- **Unknown patterns:** Pipeline stops with a CoreGap report (see below).

---

## What's Deterministic vs. What's Judgment

The pipeline separates deterministic logic (repeatable, testable Python code) from LLM judgment (ambiguity resolution, web search, diagnosis).

| Step | Deterministic (Python function) | Judgment (LLM) |
| ------ | -------------------------- | ----------------- |
| HAR validation | Structural checks, auth flow detection — fail-fast gate | — |
| Fleet scan | `scan_fleet()` builds patterns from catalog parser.yaml files | — |
| Transport detection | HNAP marker scan, URL pattern matching | — |
| Auth detection | Pattern matching against `auth_patterns.json` | Ambiguous cases presented to user |
| Format detection | HNAP: deterministic. HTTP: candidate list | HTTP: LLM reads response bodies, picks format |
| Field mapping | Column/field extraction from HAR content, fleet patterns augment direction and system_info label detection | — |
| Metadata enrichment | Inference from analysis + defaults | Web search for missing fields (chipset, ISPs) |
| Config generation | Pydantic validation, constraint checking | Fix validation errors and retry |
| Golden file generation | Parse HAR through config | Sanity-check channel counts |
| Testing | HAR replay, golden file diff | Diagnose failures, fix config |

See [ONBOARDING_SPEC.md § Tool boundaries](ONBOARDING_SPEC.md#tool-boundaries) for the full responsibility matrix.

---

## CoreGap: When the Pipeline Stops

A **CoreGap** means the modem uses a pattern that Core doesn't support yet. The pipeline detects it, reports it, and stops. No guessing, no workarounds.

| Gap Category | What It Means | What Core Needs |
| ------------- | --------------- | ----------------- |
| `unmatched_login` | Login POST to an endpoint not in known patterns | New URL pattern in `auth_patterns.json`, or a new auth strategy |
| `auth_unknown` | Auth mechanism doesn't match any known strategy | New auth strategy implementation |
| `unmatched_restart` | Restart action to an unrecognized endpoint | New URL pattern in `action_patterns.json` |
| `unmatched_logout` | Logout action to an unrecognized endpoint | New URL pattern in `action_patterns.json` |

Well-known modems with standard patterns produce zero gaps. Novel modems produce gaps that require a development effort before onboarding can proceed.

When the pipeline stops on a gap, the report contains enough detail (phase, category, summary, wire evidence) to file a GitHub issue for the development work.

---

## Fleet Patterns (Layer 2)

The pipeline uses a three-layer detection model:

1. **Core baseline** — deterministic heuristics built into `analyze_har`
2. **Fleet patterns** — proven patterns extracted from existing catalog entries
3. **LLM gap-fill** — judgment calls for ambiguous cases

`scan_fleet()` reads all `parser.yaml` files in the catalog and builds a `FleetPatterns` instance containing selector-to-direction mappings, system_info label/ID/JSON-key mappings, delimiters, channel type values, and aggregate field patterns. This is passed to both `analyze_har(fleet=...)` and `generate_config(fleet=...)`.

Fleet patterns grow automatically as new modems are onboarded — each new parser.yaml enriches detection for future modems that share similar patterns.

---

## Data-Driven Extension Points

Two JSON pattern files control what the pipeline recognizes. Adding support for a new login URL or action endpoint is a data change, not a code change:

- **`auth_patterns.json`** — known login URL patterns and credential field names. When `analyze_har` sees a POST to a URL matching a pattern here, it classifies the auth strategy.

- **`action_patterns.json`** — known action URLs (logout, restart, reboot). When `analyze_har` sees POST requests matching patterns here, it maps them to modem actions.

Both files live in Catalog Tools (`solentlabs/cable_modem_monitor_catalog_tools/analysis/`). Extending them is the first step when a CoreGap is reported for an unmatched endpoint.

---

## Where Things Live

| Artifact | Location |
| ---------- | ---------- |
| Pipeline tools (validate, analyze, enrich, generate, test) | `packages/cable_modem_monitor_catalog_tools/solentlabs/cable_modem_monitor_catalog_tools/` |
| Pattern files (auth, actions) | `.../catalog_tools/analysis/auth/` and `.../catalog_tools/analysis/actions/` |
| Fleet scanner | `packages/cable_modem_monitor_catalog_tools/solentlabs/cable_modem_monitor_catalog_tools/fleet_scanner.py` |
| Intake pipeline regression (accuracy tracking + auth audit) | `packages/cable_modem_monitor_catalog_tools/scripts/intake_pipeline_regression.py` |
| Test harness (HAR replay, golden file comparison) | `packages/cable_modem_monitor_core/solentlabs/cable_modem_monitor_core/test_harness/` |
| Modem catalog entries (output) | `packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/{manufacturer}/{model}/` |
| Authoritative spec | `packages/cable_modem_monitor_catalog_tools/docs/ONBOARDING_SPEC.md` |
| Runnable workflow | [MODEM_INTAKE_WORKFLOW.md](MODEM_INTAKE_WORKFLOW.md) |

---

---

## Intake Pipeline Regression

`scripts/intake_pipeline_regression.py` measures how well the pipeline
reproduces committed catalog configs when run against the same HAR as a
fresh submission. It is a reporting tool for onboarding capability and,
in baseline mode, a **ratchet gate**: the committed fleet baseline at
`scripts/intake_baseline.json` records each modem's pipeline status and
action grades, and `make intake-regression` (run by `validate-ci` and
mirrored in CI) fails when any of them gets worse. Findings indicate
where the intake pipeline — or the capture, to be resolved in
har-capture — can improve, not regressions in Core.

```bash
python packages/cable_modem_monitor_catalog_tools/scripts/intake_pipeline_regression.py
python packages/cable_modem_monitor_catalog_tools/scripts/intake_pipeline_regression.py --modem arris/sb8200 -v
python packages/cable_modem_monitor_catalog_tools/scripts/intake_pipeline_regression.py --scorecard scorecard.json
python packages/cable_modem_monitor_catalog_tools/scripts/intake_pipeline_regression.py --baseline packages/cable_modem_monitor_catalog_tools/scripts/intake_baseline.json
```

**What it reports:**

| Status | Meaning |
|--------|---------|
| `CLEAN` | Generated golden file matches committed golden file exactly |
| `DRIFT` | Pipeline ran but generated output differs from committed golden file |
| `FAILURE` | Pipeline stage failed (validate_har, analyze_har, generate_config) |

Fleet-wide **field accuracy** is reported as a percentage of committed
golden file fields correctly reproduced by the pipeline. This tracks
improvement over time as the pipeline gains new pattern recognition.

**Actions grading** compares pipeline-detected logout/restart actions
against the committed modem.yaml per HAR
(`analysis/actions/grading.py`):

| Grade | Meaning |
|-------|---------|
| `match` | Type, identity (method + endpoint, or hnap action_name), and params all reproduced |
| `partial` | Identity matches; params differ, are missing, or json_body not produced |
| `pipeline_only` | Pipeline detected an action the catalog never adopted — candidate enrichment, or a false positive |
| `committed_only` | Committed action the pipeline cannot produce from the HAR (human-authored config, or action never fired during capture) |
| `mismatch` | Type, endpoint, method, or action_name disagree — investigate which side is wrong |

Human-authored fields a HAR cannot show (`pre_fetch_action`,
`action_auth`, `requires_session`, response keys) are out of grading
scope.

**Auth grading** compares the pipeline-generated auth block against the
committed modem.yaml (`analysis/auth/grading.py`), using the same grade
taxonomy on two items: `strategy` (the detected auth strategy — the
headline capability) and `fields` (everything else in the block —
endpoints, field names, cookie names, nested success criteria). Fields
are only graded when the strategy matches; comparing field layouts of
two different strategies is meaningless. Unlike actions (graded from
analysis output), auth is graded from the generated config, so it
requires generation to succeed.

**Auth fixture audit** runs at the end of every sweep. For each form-auth
modem with `login_page` configured, it verifies that the committed HAR
fixture contains a usable login page response. Issues are printed as
advisory — they indicate catalog gaps to investigate, not CI failures.
Hardware is required to confirm whether a fixture gap actually causes a
runtime problem.

**Regression baseline mode** (`--baseline`) fails only when a modem's
pipeline status or an action grade gets worse than the recorded
baseline, or a new modem arrives with non-clean status or non-match
grades. Use `--update-baseline` to refresh
`scripts/intake_baseline.json` after a deliberate improvement or a new
intake, and commit the file with that change — the baseline diff is the
durable record of what moved.

The ratchet machinery (baseline load/save/compare, scorecard, result
classification) lives in the unit-tested
`solentlabs/cable_modem_monitor_catalog_tools/regression/` package and
is generic over grade dimensions; the script supplies discovery,
pipeline stages, and printing. The shared grade taxonomy is
`solentlabs/cable_modem_monitor_catalog_tools/grading.py`.

---

## Further Reading

- [ONBOARDING_SPEC.md](ONBOARDING_SPEC.md) — full tool contracts, decision tree (7 phases), validation rules, worked examples, error handling
- [MODEM_REQUEST.md](../../../docs/MODEM_REQUEST.md) — contributor guide for submitting HAR captures
- [MODEM_YAML_SPEC.md](../../cable_modem_monitor_core/docs/MODEM_YAML_SPEC.md) — modem config schema and transport constraints
- [PARSING_SPEC.md](../../cable_modem_monitor_core/docs/PARSING_SPEC.md) — parser config schema
