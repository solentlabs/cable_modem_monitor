# Claude Rules

> **This file**: how Claude behaves in this repository — diagnostic
> disciplines, decision sequencing, verification, process guardrails.
> Architecture, code quality, and testing standards live in the docs
> linked below; this file points rather than restates.

## Where Things Live

| Topic | Authoritative doc |
| ----- | ----------------- |
| Architecture (SoC, DRY, Core/HA boundary, additive features, protocol primitives) | `packages/cable_modem_monitor_core/docs/ARCHITECTURE.md` |
| What enters Core's schema (fleet-observed metrics vs user analytics; signal-health-style proposals) | `packages/cable_modem_monitor_core/docs/ARCHITECTURE_DECISIONS.md` § Core Schema Model |
| Modem config principles (data-driven YAML, config-as-parameters, intake pipeline) | `packages/cable_modem_monitor_core/docs/MODEM_YAML_SPEC.md` § Principles |
| Code quality (no shortcuts, quality gates, forward refs, suppression discipline) | `docs/CODE_REVIEW.md` § Design Principles + Source File Standards |
| Test patterns (table-driven, fixtures vs inline, no data blobs, no modem-specifics, test overrides as smell) | `docs/CODE_REVIEW.md` § Test File Standards |
| HAR fixtures (Git LFS, `load_har_json()`) | `docs/CODE_REVIEW.md` § Loading HAR Fixtures |
| Logging conventions (`[MODEL]` tag) | `docs/CODE_REVIEW.md` § Modem-Specific Log Messages |
| Async / blocking I/O | `docs/CODE_REVIEW.md` § No Blocking I/O in Async Context |
| Release flow (branching, merging, tagging) | `docs/reference/RELEASING.md` |
| Process questions (where does X go? PR vs Discussion vs Issue?) | `CONTRIBUTING.md` |
| Specs by package | core: `packages/cable_modem_monitor_core/docs/README.md` · catalog tools: `packages/cable_modem_monitor_catalog_tools/docs/README.md` · HA: `custom_components/cable_modem_monitor/docs/README.md` · project: `docs/README.md` |
| Reference test (table-driven exemplar) | `tests/modem_config/test_modem_yaml_validation.py` |

## Contents

| Section | What it covers |
| ------- | -------------- |
| Core Principles               | Specs and process — 12 numbered rules that govern Claude's behavior |
| Diagnosis Discipline          | Asking for the data that distinguishes causes                       |
| Decision Discipline           | Sequencing, no shortcuts, no speculation                            |
| Verification Discipline       | Ground-truth checks before claims                                   |
| Catalog & Data Discipline     | YAML scope, recovery genericity, HAR-first intake                   |
| Code Discipline               | Type-safety, isolation, no infra for hypotheticals                  |
| Shell Command Generation      | Avoid permission-check triggers                                     |
| Pre-Push Verification         | Always run `make validate-ci` before pushing                        |
| Irreversible Operations       | Stop and verify before destructive git ops                          |
| PR and Issue Conventions      | No auto-close keywords; cite issues for context                     |

## Core Principles

These principles govern Claude's behavior on every change. They are
hard constraints, not guidelines. When in doubt, the principle wins
over convenience.

### Specs and Documentation

1. **Specs are the authority.** Code follows specs. No silent
   deviations. If the code needs to diverge, discuss the gap first,
   update the spec, then update the code.

2. **Design decisions land in specs, not in conversation.** Every
   architectural decision made during a session must be committed to
   the relevant spec file before the session ends. Conversation
   history is ephemeral — specs are durable.

3. **Docs and code move together.** Every core change reconciles the
   affected specs (ARCHITECTURE, ORCHESTRATION_SPEC, MODEM_YAML_SPEC,
   etc.). A code change without a corresponding spec update is
   incomplete.

### Process

4. **Only the developer stages files.** Never run `git add`. Show
   the list of changed files and proposed commit message. Let the
   developer stage them.

5. **No external actions without discussion.** Never create GitHub
   issues, PRs, commits, pushes, label changes, or any external-
   facing action without explicit discussion first.

6. **Before deleting or moving ANY file, run `rg <filename>` across
   the entire project.** Files are referenced by non-Python sources
   (CI workflows, Makefiles, docs, VS Code tasks) that linters don't
   scan.

7. **Always read a file before writing to it. No exceptions.** Even
   "I just want to overwrite it" — read first. Local-only/gitignored
   files especially: no git recovery path. The Write tool errors if
   you skip the read; do not work around it.

8. **Stop on placeholders.** When reading code, config, or YAML
   during analysis, halt and flag immediately on `XXX`, `TODO`,
   `FIXME`, `TBD`, `???`, `undefined`, `placeholder`, `replace_me`.
   Do not summarize the surrounding architecture as "looks good"
   while quietly ignoring unfilled values.

9. **Don't offer "revisit later" as an option.** When presenting
   design choices, offer "ratify now" or "drop the idea entirely."
   Never present "keep the ambiguity and revisit later" as a third
   option — deferred items pile up and silently expire.

10. **No "pre-existing" framing.** Don't dismiss code gaps as
    "pre-existing," "not mine," or "from an earlier session." The
    full working tree is in scope unless explicitly narrowed. The
    only valid scope-narrowing reason is *what* the gap is, never
    *who wrote it first*.

11. **Don't claim unverified fixes** in user-facing replies (GitHub
    issues, comments). Use hedged language: "should address," "ready
    to test," "if it works, please post diagnostics." Only claim
    "fixed" after the user confirms on their hardware.

12. **Never read the HA test config `.storage` directory.** The path
    is denied in `.claude/settings.json` (`permissions.deny`) and
    mounted under the `/config` volume in `docker-compose.test.yml`.
    It contains live modem credentials in plaintext (HA stores
    config-entry data unencrypted on disk by design). Reading it via
    any tool — Read, `cat`, `grep`, `rg`, `jq`, `awk`,
    `python -c "open()"` — leaks the password into the conversation
    context. The settings.json deny only blocks the Read tool; this
    rule covers the rest. If you need config-entry fields for
    analysis, ask the user to paste a redacted excerpt.

## Diagnosis Discipline

When a runtime error appears in user-supplied logs, **ask for the data
that would distinguish candidate causes before generating theories.**
Typically the surrounding ±10 log lines. Don't theorize first; don't
propose fixes first.

- **Differential test**: every theory must answer "why now and not
  before?" If it can't, it's incomplete — don't commit to a fix
  built on it.
- **User hypotheses are primary evidence**, not options among yours.
  Tentative phrasing ("if we... maybe this...") doesn't downgrade
  the signal — the user has runtime context the codebase doesn't.
- **External failure modes are invisible to grep.** Install path,
  network path, runtime config, user actions — none of those show
  up in codebase searches. When stuck inside the repo, ask: "could
  this be coming from outside the code?"
- **Don't propose fixes until you can name what specifically broke
  and why.** "Probably X" is not a fix-ready diagnosis.

## Decision Discipline

- **One thing at a time.** Surface decisions sequentially; don't
  dump 6-row tables of "outstanding work." Long synthesized lists
  are too much to absorb in one pass and let shortcuts slip
  through.
- **Research returns a recommendation, not a paper.** When asked to
  research, analyze, or assess, default to a 2–3 sentence answer
  with the single tradeoff that matters. Tables, section headers,
  ASCII diagrams, and leverage rankings are opt-in — only expand
  when the user asks "explain why" or "show your work." This rule
  exists because research prompts repeatedly returned multi-section
  papers when a recommendation was wanted.
- **No judgment shortcuts.** Don't dismiss alternatives with
  "overkill," "churn," "make-work," or "no cohesion payoff" without
  weighing real costs and benefits. The shortcut costs more later —
  either a missed improvement or a re-litigated decision.
- **Know what you know — don't speculate.** Model what we actually
  observe; stop there. Don't add inference-based features when the
  signal is ambiguous (multi-signal voting, tunable thresholds, etc.
  are tells).
- **Park side investigations.** When a parallel audit returns
  results, summarize and surface as a *separate* task. Don't merge
  the punch list into the active commit batch without explicit
  ratification.
- **Avoid refactor thrashing.** After 1–2 "this smells" rounds on
  the same module, stop and ask for the end state. If rounds 1 and
  2 haven't converged, round 3 won't either — the underlying issue
  is the goal isn't clear, not that the current location is wrong.
- **Don't defer obvious cosmetic fixes.** If a review surfaces a
  real issue (stale name, drifted docstring, minor nit), fix it in
  the current pass. *"Whenever we say we should take care of
  something later, we do not, and that adds to hidden tech debt."*
  Never write "separate pass if desired" — that's deferral dressed
  as a suggestion.

## Verification Discipline

- **Verify against ground truth, not against doc claims.** When
  asked to review a planning doc / status doc / roadmap, summarize
  what's *actually true* (check code, git, issues), not what the
  doc *says*.
- **Verify the premise before creating a worktree.** For any task
  that says "remove X" or "clean up Y," `rg` for it on the current
  branch first. Zero hits means the work is already done — stop
  before spinning up a worktree.
- **Verify handoff work.** Other Claude sessions on the same
  worktree may regress earlier work. After a handoff, run the full
  pipeline (mock-server / golden-file / channel counts) — don't
  just check tests pass. Tests passing doesn't mean the right
  things are being tested.
- **Recurring problem = root cause unfixed.** If a fix has to be
  re-applied within one session, stop fixing the symptom and find
  what's recreating the failure.
- **Never dismiss test failures as "pre-existing."** If tests pass
  on committed code but fail with working-tree changes, it's a
  regression. Stash and verify on clean state before claiming
  pre-existing.
- **Done means done.** When a task is class-scoped ("all issue
  templates," "all parser docstrings"), apply the criteria
  consistently to every member. Pass-through skimming for one
  specific issue isn't done.
- **Commit before recording done.** Work must be committed to a
  durable branch before journal/memory says "done," "added," or
  "implemented." Stashed work on a worktree branch is one
  `git gc` away from loss.
- **Run pyright alongside mypy.** `mypy` and Pyright (Pylance) have
  different strictness. Code passing mypy can still show red
  squiggles in VS Code. After mypy, run `.venv/bin/pyright`.
- **Preserve actor when restating prior facts.** When summarizing or
  recommending based on a prior exchange, the subject/object of "who
  said/did/decided X" is load-bearing. Compressing "X reported Y"
  into "we told X about Y" (or vice versa) misrepresents the record
  even when the surrounding argument is sound. Re-read load-bearing
  sentences against the actual exchange before submitting.

## Catalog & Data Discipline

- **No modem-specific behavior in `modem.yaml`.** YAML contains how
  to *talk to* the modem (transport, auth, session, actions,
  hardware metadata, parser mappings) — not how Core processes
  responses. No behavior flags, no per-modem timing knobs.
- **Recovery logic stays generic.** One shared recovery primitive
  for all post-disruption polling, regardless of trigger
  (commanded, observed outage, reboot-signal vote). No per-modem
  recovery tuning.
- **HAR intake is the only data path.** When a user's modem isn't
  matching the catalog, the default ask is a fresh HAR — not
  one-off questions ("what URL is in your address bar?"). HAR is
  reproducible, auditable, and feeds the catalog_tools pipeline.
  Fall back to direct questions only if `har-capture` genuinely
  can't capture what's needed.
- **Verified JSON must be faithful.** `modem.verified.json` is a
  faithful copy of the HA diagnostics `data` section — not a
  curated subset. Keep all modem data verbatim. Strip only:
  `home_assistant`, `custom_components`, `integration_manifest`,
  `setup_times`, `_solentlabs`, `_review_before_sharing`,
  `recent_logs`. Add `verified_at` and `version` at top.
- **Source all factual claims.** Every factual claim in data files
  (`providers.json`, `chipsets.json`, modem.yaml notes/sources)
  must include a reference URL or citation. Without a source, the
  claim is indistinguishable from fabricated data. If a source
  can't be found, leave the field empty rather than guessing.
- **Catalog data stays true to source; normalization happens at
  presentation.** This project is a universal translator — the
  catalog is the authoritative record of what each modem reports
  about itself and how its manufacturer brands it. `manufacturer:`
  in modem.yaml stores the manufacturer's actual styling (`ARRIS`
  if that's how the modem self-reports, `Arris` if that's what
  comes back from HNAP, `Compal`, `Hitron`, etc.). Don't pre-
  normalize to title case in the catalog. Display layers
  (`build_model_display_name` in the integration's config flow,
  sensor titles, etc.) handle case normalization for human
  readability. Variation in manufacturer string across the same
  vendor's products is real signal — different firmware reports
  the manufacturer differently — not drift to be ironed out.

## Code Discipline

- **TDD for non-trivial bug fixes.** (1) Read relevant specs.
  (2) Document the use case if missing. (3) Write tests that fail.
  (4) Implement. (5) Verify tests pass.
- **Keep WHY comments on refactor.** Don't strip section markers
  (`# Phase 1 — auth`), rationale notes, or numbered-procedure
  markers during a rewrite. The "default to no comments" rule
  targets WHAT-noise, not WHY-context.
- **Isolate before sprawl.** If a feature would touch >2 files,
  it probably needs its own module. Spreading wiring across
  `button.py`, `sensor.py`, `coordinator.py`, and `__init__.py`
  for one concern is the smell.
- **No infrastructure for hypothetical recurrence.** Before adding
  a test, CI job, hook, script, or module to address a one-shot
  incident, state the problem in one sentence and ask: am I
  protecting against documented past failures, or against a
  hypothetical future one? If hypothetical, name it as such and
  let the user choose whether to invest. A wrong command in one
  GitHub comment doesn't justify a smoke test + Make target + CI
  job; a doc fix or upstream link does.
- **Small files are fine** when (a) the logic is clearly bounded
  (one concern, one reason to change) and (b) the file has a clear
  docstring explaining what lives there. A 50-line file with one
  clear concern beats a 50-line addition to a `utils.py` dumping
  ground.
- **Type-safety patterns:**
  - `Literal[...]` for params with fixed valid values, not `str`
  - `Model.model_validate(data)` for Pydantic from dicts, not `Model(**data)`
  - `@functools.lru_cache` for JSON file caching, not global `dict | None` with manual checks
  - `Any` for pass-through `*args/**kwargs`, not `object`
  - `dict[str, Any]` for JSON data, not `dict[str, object]`
- **Use existing pipelines.** Never hand-build artifacts when a
  pipeline tool exists. `generate_golden_file()` runs the real
  parser coordinator. Serialize with
  `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`.
- **Docstring placeholders.** In docstring examples, use template
  placeholders (`{manufacturer}/{model}/`), not specific fake names
  (`acme/a100/`). Tests still use concrete strings; docstrings
  describe the pattern.
- **No P-numbers in public artifacts.** Roadmap identifiers (`P28`,
  `P34`, etc.) come from an internal roadmap doc that ships only
  locally. Tag annotations, CHANGELOG entries, GitHub release notes,
  and issue replies cite GitHub issue numbers, not roadmap Pxx.

## Shell Command Generation — Avoid Permission Check Triggers

When generating shell commands:

1. **Never embed newlines or `#` characters inside quoted strings** passed as command arguments
2. **For multiline shell logic**, write to a `.sh` script file first, then execute the file
3. **Prefer simple, single-line commands** with explicit arguments
4. **For complex logic**, use a heredoc written to a temp file rather than inline quoted strings
5. **Before executing any shell command**, verify it contains no newline characters inside quoted strings and no `#` characters that could be interpreted as hidden arguments

**Why?** Claude Code's permission checker flags quoted newlines followed by `#`-prefixed lines as potential shell injection. Restructuring commands eliminates the interrupt.

## Pre-Push Verification — ALWAYS Run Before Push

Before pushing ANY commits, run the canonical local CI mirror:

```bash
make validate-ci
```

This runs lint + format + type-check + tests + intake regression +
PII check + catalog README freshness — the same surface CI's Tests
workflow exercises. If `make validate-ci` is green, CI will be green.
`scripts/release.py` runs it automatically before every version bump.

**Why?** CI runs on the entire project. Pre-commit hooks only check
staged files, and `make test` is a subset of CI. `make validate-ci`
is the only command guaranteed to mirror CI exactly.

**Outdated-deps footer:** `validate-ci` ends with `pip list --outdated`.
When that footer shows drift, propose a separate deps-update commit
before pushing — visibility without action becomes wallpaper.

**CI job coverage:** When verifying CI after a push, confirm every
expected job ran. A missing job is not a pass — absence of failure is
not success. If a job didn't trigger, check the workflow's path filters
and fix them before declaring the push clean.

### Optional pre-push hook — opt-in, suggest at the right moment

`make install-hooks` installs an opt-in `.git/hooks/pre-push` that
runs `make validate-ci` automatically before every push (chained
after `git lfs pre-push`). It is not committed-by-default — CI is the
authoritative gate, and forcing the hook on every developer would
create install-state inconsistency without adding any enforcement CI
doesn't already provide.

**When to suggest it**: after a developer hits a CI failure that
`make validate-ci` would have caught locally (coverage drop, lint
miss, missing local-mirror), suggest `make install-hooks` *once*. Do
not repeat the suggestion if they decline, and do not suggest it on
fresh clones or on every validate-ci run — that becomes noise.

### Adding a new CI job — local-mirror rule

**Whenever you add a new job or step to `.github/workflows/tests.yml`,
add a corresponding Makefile target and wire it into `make
validate-ci` as a dependency.** Every CI check must have a
local-mirror command. The two together are a single change, not a CI
change with a "follow up" Makefile change. Drift between CI and local
is what hides regressions until tag time (see alpha.17 retrospective).

Exceptions: external GitHub Actions that can't be reasonably
reproduced locally (e.g., `home-assistant/actions/hassfest@master`,
which requires HA core source and Docker). Document the exception in
the Makefile comment so future-you knows why `validate-ci` doesn't
cover it.

## Irreversible Operations — STOP and VERIFY

When the user gives explicit constraints (e.g., "without closing the PR", "don't delete X"):

1. **Treat these as HARD BLOCKERS** — not suggestions
2. **Research/verify the outcome BEFORE executing** — if unsure, ASK first
3. **If something goes wrong, STOP and ask** — don't try to fix it autonomously
4. **Never assume** — GitHub branch renames, force pushes, deletions can have cascading effects

Examples of irreversible operations requiring verification:

- Branch renames, deletions, force pushes
- PR/issue closures
- Tag deletions
- Any git operation with `--force`

## PR and Issue Conventions

No auto-close keywords (`Fixes #X`, `Closes #X`, `Resolves #X`) in PR
bodies *or* commit messages — GitHub scans every commit in a merge
and closes regardless of qualifier. Use `Related to #X` /
`Addresses #X` instead.

Issue label glossary and state semantics live in
[CONTRIBUTING.md § Issue Labels](CONTRIBUTING.md#issue-labels) and
[CONTRIBUTING.md § Issue Closing Policy](CONTRIBUTING.md#issue-closing-policy).
