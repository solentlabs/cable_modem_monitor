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
| Logging conventions (event taxonomy, `log_event()`) | `packages/cable_modem_monitor_core/docs/LOGGING_SPEC.md` |
| Async / blocking I/O | `docs/CODE_REVIEW.md` § No Blocking I/O in Async Context |
| Release flow (branching, merging, tagging) | `docs/reference/RELEASING.md` |
| Process questions (where does X go? PR vs Discussion vs Issue?) | `CONTRIBUTING.md` |
| Doc authoring (one home per rule, current contract only — no version history, what earns an ADR entry, cross-linking) | `docs/README.md` § Doc Authoring |
| Specs by package | core: `packages/cable_modem_monitor_core/docs/README.md` · catalog tools: `packages/cable_modem_monitor_catalog_tools/docs/README.md` · HA: `custom_components/cable_modem_monitor/docs/README.md` · project: `docs/README.md` |
| Reference test (table-driven exemplar) | `tests/lib/test_parse_host_input.py` |
| Path-scoped rules and skills | `.claude/rules/` (load when matching files are touched) · `.claude/skills/` (invoked) |

## Core Principles

These principles govern Claude's behavior on every change. They are
hard constraints, not guidelines. When in doubt, the principle wins
over convenience.

### Specs and Documentation

- **Specs are the authority.** Code follows specs; no silent deviations.
  If code must diverge, discuss the gap, update the spec, then the code.
- **Design decisions land in specs, not in conversation.** Commit every
  architectural decision to the relevant spec before the session ends;
  conversation is ephemeral, specs are durable.
- **Docs and code move together.** A core change reconciles the affected
  specs (ARCHITECTURE, ORCHESTRATION_SPEC, MODEM_YAML_SPEC, etc.); code
  without its spec update is incomplete.
- **Write for clarity and brevity, then cut again.** Before committing
  prose (spec text, generated-doc copy, comments, commit bodies), delete
  throat-clearing openers, restated context, hedges and clauses that
  repeat a neighbour. Say it once in the fewest words that keep it true;
  a definition read twice gets asked about again. Apply it to the first
  draft: verbose text ships and nobody trims it.

### Two READMEs — GitHub vs HACS (do not consolidate)

`.github/README.md` is the GitHub landing page; the root `README.md` is
what HACS renders. They serve different surfaces, so do not merge them.
HACS resolves no repo-relative paths, so the root README uses absolute
URLs only; links in `.github/README.md` must resolve from `.github/` or
be absolute. `make link-check` (in `validate-ci`) enforces both.

### Process

- **Only the developer stages files.** Never run `git add` (denied in
  settings). Show the changed files and a proposed commit message; the
  developer stages them.
- **No external action without discussion, per action.** No GitHub
  issue, PR, commit, push, label change or other external-facing action
  without explicit discussion first. Plan approval is not approval of the
  action: confirm again immediately before executing it. Iterating on
  draft text is drafting, not authorization, even when the developer
  supplies the final wording; only "post it" / "send it" authorizes the
  call. Local actions (edits, tests, lint) inherit plan-level approval.
- **Before deleting or moving a file, `rg <filename>` across the
  project.** Non-Python sources (CI workflows, Makefiles, docs, VS Code
  tasks) reference files and linters don't scan them. When a task label
  or path changes in `.vscode/tasks.json`, also audit
  `scripts/dev/next_steps.txt`, `scripts/dev/welcome_message.txt`,
  `.devcontainer/post-start.sh` and `docs/setup/GETTING_STARTED.md`;
  drift there is invisible to linters and breaks the contributor on-ramp.
- **Stop on placeholders.** Halt and flag `XXX`, `TODO`, `FIXME`, `TBD`,
  `???`, `undefined`, `placeholder` or `replace_me` met while reading
  code, config or YAML. Don't call the surrounding architecture "looks
  good" while ignoring unfilled values.
- **Don't offer "revisit later".** Offer "ratify now" or "drop the idea
  entirely"; deferred items pile up and silently expire.
- **No "pre-existing" framing.** Don't dismiss a gap as "pre-existing",
  "not mine" or "from an earlier session". The working tree is in scope
  unless explicitly narrowed, and the only valid reason is what the gap
  is, never who wrote it first.
- **Don't claim unverified fixes** in user-facing replies. Say "should
  address", "ready to test", "if it works, please post diagnostics";
  claim "fixed" only after the user confirms on their hardware.
- **Never read the HA test config `.storage` directory with any tool.**
  Settings deny only the Read tool; `cat`, `grep`, `rg`, `jq`, `awk` and
  `python -c` would leak the plaintext modem credentials too. For
  config-entry fields, ask the user to paste a redacted excerpt.

## Diagnosis Discipline

When a user supplies a log, a runtime error or a bug report, invoke the
`diagnose-user-report` skill before replying. Its core, which applies
even if you skip it:

- **Ask for the data that would distinguish candidate causes before
  theorizing or proposing a fix**, typically the surrounding ±10 log
  lines.
- **Every theory must answer "why now and not before?"**
- **User hypotheses are primary evidence**, not options among yours.
- **Don't propose a fix until you can name what specifically broke and
  why.** With no reproduction or hardware, the deliverable is an
  evidence ledger of what is closed and what is open, not a
  recommendation.

## Decision Discipline

- **One thing at a time.** Surface decisions sequentially; no 6-row
  tables of "outstanding work", which are too much to absorb and let
  shortcuts slip through.
- **Research returns a recommendation, not a paper.** When asked to
  research, analyze or assess, default to 2–3 sentences with the single
  tradeoff that matters. Tables, headers, Phase-numbered scaffolding,
  ASCII diagrams and leverage rankings are opt-in: expand only on
  "explain why" or "show your work."
- **Structure over presentation.** Data model and schema first;
  presentation polish after.
- **No judgment shortcuts.** Don't dismiss alternatives with "overkill",
  "churn", "make-work" or "no cohesion payoff" without weighing real
  costs; the shortcut costs a missed improvement or a re-litigated
  decision.
- **Know what you know — don't speculate.** Model what we observe and
  stop. Inference features on an ambiguous signal (multi-signal voting,
  tunable thresholds) are tells.
- **Park side investigations.** Summarize a parallel audit's results and
  surface them as a separate task; don't merge its punch list into the
  active commit batch without ratification.
- **Avoid refactor thrashing.** After 1–2 "this smells" rounds on a
  module, ask for the end state; if a third round would follow, the goal
  is unclear, not the location.
- **Don't defer obvious cosmetic fixes.** Fix a real issue a review
  surfaces (stale name, drifted docstring, nit) in the current pass:
  *"Whenever we say we should take care of something later, we do not,
  and that adds to hidden tech debt."* Never write "separate pass if
  desired".
- **Name the governing spec before recommending anything in its
  subsystem, and say which one you read.** Code and tests are not a
  substitute: the `AUTH_LOCKOUT` mapping was assessed from the signal
  enum, the HA error map and 12 locale files, and the real finding was
  in `AUTH_HNAP_SPEC.md`, never opened. Saying the spec out loud makes
  an omission visible at a glance.
- **Don't manufacture urgency.** Inflating a remote edge case into a
  release gate closes a question instead of weighing it. Rank a gap by
  what it is and costs, and say plainly whether it blocks the current
  cut. (Dismissing a gap by authorship is under Process.)

## Verification Discipline

The first three rules put the check in the reply, where a skipped one is
visible without re-running the work.

- **Cite what you opened.** When stating a fact or cause about the
  system, name the files or commands it rests on, and their extent
  ("read: the last 3 comments" differs from "read: the thread"). If the
  sources don't cover the claim's domain the hole shows: "CI isn't
  recording the trend (checked: Makefile, the regression script)" is
  visibly unsupported, since neither is CI. This holds for draft public
  text too, including claims the user supplied: each factual claim
  carries its source when the draft is presented, not when it is posted.
- **An unexplained number stays unexplained.** Report the measurement;
  don't supply an unverified cause. "I can't account for this yet" is a
  complete answer. (2026-07-29: every measurement was correct and every
  wrong conclusion was an invented cause laid over one, each disproved
  by a single `git log` or `grep`.)
- **Review your own diff before declaring it done.** For a change to
  runtime behavior (policy, auth, orchestration, recovery), re-read the
  full diff as a reviewer hunting for what it breaks, and name in the
  reply the failure mode you looked for. Green gates are not this check:
  all were green on the #185 auth change while it would have posted
  credentials six times at an unknown device and shown the user the
  wrong remedy.
- **Verify against ground truth, not doc claims.** Reviewing a planning,
  status or roadmap doc: summarize what is actually true (code, git,
  issues), not what the doc says.
- **Read what already shipped before proposing an edit to it.** Before
  recommending a change to a catalog entry, spec or doc, run
  `git log --follow` on the target and grep CHANGELOG.md for its subject:
  its last commit was often written to settle the question you are about
  to reopen.
- **Empty output is not an empty set.** Never assert absence from a
  command whose output you haven't confirmed is well-formed (totev#313
  was reported "closed same day, no comments" when two comments reversed
  the reading).
- **Verify the premise before creating a worktree.** For "remove X" or
  "clean up Y", `rg` for it on the current branch first; zero hits means
  it is already done.
- **After a hand-off, audit the full diff before touching anything**
  (`git diff HEAD --stat`): the gitStatus snapshot can be stale, and
  another session may have regressed earlier work.
- **Never spawn a sub-agent to implement a feature that touches existing
  code, specs or tests.** Sub-agents lack project history and make
  unsolicited cleanup decisions (removing fields, dropping coverage,
  stripping docs). Only bounded read-only research is safe; if context
  pressure makes direct implementation tempting, split the task into
  smaller sessions.
- **Recurring problem = root cause unfixed.** If a fix has to be
  re-applied within a session, find what is recreating the failure.
- **Never dismiss test failures as "pre-existing".** If tests pass on
  committed code but fail with working-tree changes, it is a regression.
  Verify against the committed code without stashing (stash is
  forbidden: global CLAUDE.md § Git); ask before creating a worktree.
- **Done means done.** For a class-scoped task ("all issue templates",
  "all parser docstrings") apply the criteria to every member; skimming
  for one issue isn't done.
- **Before journal or memory says "done", the work is committed** (with
  the developer's authorization): stashed work is one `git gc` from loss.
- **Run pyright alongside mypy.** Pyright is stricter in places: after
  mypy, run `PYRIGHT_PYTHON_FORCE_VERSION=latest .venv/bin/pyright` over
  every file in `git status`, tests included, unprompted, before
  declaring a work unit done.
- **Preserve actor when restating prior facts.** "X reported Y"
  compressed into "we told X about Y" misrepresents the record even when
  the argument is sound; re-read load-bearing sentences against the
  actual exchange.

## Catalog & Data Discipline

- **HAR captures are immutable evidence.** Never edit one — broken
  markup is firmware behavior the parser must handle. Full policy:
  `packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md`
  § HAR Captures Are Immutable Evidence.
- **No modem-specific behavior in `modem.yaml`.** Config selects and
  parameterizes Core behaviours: no behavior flags, no per-modem recovery
  timing or thresholds. The request `timeout` is the one per-modem timing
  value (`ARCHITECTURE_DECISIONS.md` § Generic timing). Recovery logic
  stays generic: all triggers reach the same code path; no per-modem
  recovery tuning. Authority: `MODEM_YAML_SPEC.md` § Principles,
  `ORCHESTRATION_SPEC.md` § Recovery.
- **HAR intake is the only data path.** When a user's modem isn't
  matching the catalog, the default ask is a fresh HAR — not
  one-off questions ("what URL is in your address bar?"). HAR is
  reproducible, auditable, and feeds the catalog_tools pipeline.
  Fall back to direct questions only if `har-capture` genuinely
  can't capture what's needed.
- Touching anything under `packages/cable_modem_monitor_catalog*/` loads
  `.claude/rules/catalog-data.md`: verified.json fidelity, sourcing
  claims in data files, the generated catalog README, and true-to-source
  catalog data.

## Code Discipline

- **TDD for non-trivial bug fixes.** (1) Read relevant specs.
  (2) Document the use case if missing. (3) Write tests that fail.
  (4) Implement. (5) Verify tests pass.
- **Fix the actual bug — no speculative migrations or renames.** AI
  drift is dangerous: a fix that "also cleans up" adjacent naming,
  structure, or config it wasn't asked to touch creates review
  burden and regressions. Scope the diff to the defect.
- **One-line function and class docstrings.** The signature and
  annotations carry the rest; a non-obvious WHY goes in an inline
  comment, contracts in the specs. Module docstrings are unaffected.
  Standard: `docs/CODE_REVIEW.md` § Public API Docstrings.
- **Keep WHY comments on refactor.** Don't strip section markers,
  rationale notes or numbered-procedure markers during a rewrite.
  Standard: `docs/CODE_REVIEW.md` § Comments on Refactor.
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
- **Type-safety patterns.** Preferred idioms (`Literal` over `str`
  enums, `model_validate` over `Model(**data)`, `lru_cache` over
  module-global caches, etc.): `docs/CODE_REVIEW.md` § Type Hints.
- **Use existing pipelines.** Never hand-build artifacts when a
  pipeline tool exists. Serialize with
  `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`.
  The golden-file procedure is in `.claude/rules/catalog-data.md`.
- **No contributor details in code.** No handles or literal user inputs
  in comments, tests or specs: cite issue numbers, use generic values.
- **No P-numbers in public artifacts.** Roadmap identifiers (`P28`,
  `P34`, etc.) come from an internal roadmap doc that ships only
  locally. Tag annotations, CHANGELOG entries, GitHub release notes,
  and issue replies cite GitHub issue numbers, not roadmap Pxx.

## Shell Command Generation — Avoid Permission Check Triggers

Newlines break allowlist matching (`Bash(gh issue view*)` will not match
a command containing one), so the permission prompt fires.

- **No newline or `#` inside a quoted command argument.** Check every
  command first. Multiline logic goes in a `.sh` file; prefer
  single-line commands.
- **`gh` JSON:** use `--jq`/`-q` (`gh issue view 152 --json title -q '.title'`).
  The `jq` binary is **not installed**: piping to it fails silently in a
  pipeline. Never pipe `gh` output to `python3 -c`.
- **Other JSON:** write to the fixed path `/tmp/claude_parse.py`
  (overwrite each time), then run `python3 /tmp/claude_parse.py`.

## Before a push

- Run `make validate-ci` and read `git log @{u}..HEAD`. validate-ci is the
  full local mirror of CI's Tests workflow; what it covers is its line in
  the Makefile, so do not restate that list elsewhere. CI runs the whole
  project, pre-commit hooks check staged files only, and `make test` is a
  subset. Commits made outside this session ride along and hit CI under
  your push: flag any in the range you did not verify.
  `scripts/release.py` runs validate-ci before every version bump.
- A green validate-ci does not guarantee a green CI: per-job settings in
  `.github/workflows/` are invisible locally.
- After the push, confirm every expected CI job ran. A missing job is not
  a pass: if one did not trigger, check the workflow's path filters and
  fix them before declaring the push clean.
- After a CI failure validate-ci would have caught, suggest
  `make install-hooks` once; not again if declined, not on fresh clones.
- Editing a workflow, the Makefile or a dependency file loads
  `.claude/rules/ci-and-dependencies.md`: the local-mirror rule for new CI
  jobs, the owned-deps check and the HA compatibility gate (never raise a
  floor above HA's pins).

## Irreversible Operations — STOP and VERIFY

When the user gives explicit constraints (e.g., "without closing the PR",
"don't delete X"):

- **Treat them as hard blockers**, not suggestions.
- **Verify the outcome before executing**; if unsure, ask first.
- **If something goes wrong, stop and ask.** Don't try to fix it autonomously.
- **Never assume.** Branch renames and deletions, force pushes (any
  `--force`), PR or issue closures and tag deletions can cascade.

## Contributor Communications

Before drafting or posting anything public in Ken's name (GitHub issues,
PRs, discussions, release notes), invoke the `contributor-comms` skill.
Its core, which applies even if you skip it:

- **Ken writes as "I"**, never "we/us/our"; there is no team. Humble,
  short, personal.
- **No LLM tells:** no "Good news:", "just landed", em-dashes, stylistic
  hyphens or "/" separators in prose.
- **State only what's verified;** inferences get "one possibility is...".
  Never write "I read the code" in Ken's voice when Claude did the
  analysis.
- **Post drafts verbatim** when Ken supplies the text.

## PR and Issue Conventions

No auto-close keywords (`Fixes #X`, `Closes #X`, `Resolves #X`) in PR
bodies *or* commit messages: GitHub scans every commit in a merge and
closes regardless of qualifier. Use `Related to #X` / `Addresses #X`.

`make autoclose-check` (in `validate-ci`) scans commit bodies only.
**PR descriptions are the vector nothing checks:** read the body yourself
before authorizing any merge to main, and flag every match as a blocker.
The parser doesn't read English: "would resolve #X if…" and "doesn't
fix #X" both close (PR #145: "still required to confirm fix resolves #81
specifically" auto-closed #81). This applies equally to a commit Claude
authored in an earlier session.

Issue labels and closing policy: [CONTRIBUTING.md § Issue Labels](CONTRIBUTING.md#issue-labels)
and [§ Issue Closing Policy](CONTRIBUTING.md#issue-closing-policy).
