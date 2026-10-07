---
name: diagnose-user-report
description: Use when a user pastes a log, traceback or error message, links a GitHub issue or bug report, reports a contributor retest result, or asks why something is failing or unreachable. Covers asking for the data that distinguishes candidate causes before theorizing, the differential test (why now and not before), user hypotheses as primary evidence, external failure modes invisible to grep, naming what specifically broke before proposing a fix, and the evidence ledger when nothing can be reproduced.
---

# Diagnose a user report

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
- **When the task cannot validate a hypothesis, the deliverable is an
  evidence ledger, not a recommendation.** Some problems have no
  reproduction, no hardware, and no way to test a theory locally
  (#120: five months, seven contributor retests, a dozen dead
  theories). In that state every session invents a fix and every fix
  collapses under the next question. Report what is closed and what is
  open, and stop. A theory closed with evidence is worth as much as a
  change and is the only progress such an issue accepts — the durable
  output of the 2026-07-27 session was its negative results, not one
  of its recommendations.
