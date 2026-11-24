#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: remind Claude to use diagnose-user-report.

CLAUDE.md § Diagnosis Discipline says to invoke the skill when a user
supplies a log, an error or a bug report. Measured over 44 sessions
(2026-10-07 to 2026-11-24), the skill fired on "look at issue N" but never
on a pasted Home Assistant log, a "why did CI fail" question or a
"user replied" notice. This hook adds a reminder when a prompt looks like
one of those. The reminder is conditional, so a false match costs one line
of context.

Reads the hook payload (JSON with a ``prompt`` field) on stdin; prints the
hook's JSON output, or nothing when no pattern matches. Never fails the
prompt: any error exits 0 silently.
"""

from __future__ import annotations

import json
import re
import sys

_PATTERNS = (
    # A pasted log line: ISO timestamp followed by a log level.
    re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\S*\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b"),
    re.compile(r"Traceback \(most recent call last\)"),
    # "why did it fail", "why am I getting errors", "how is the failure unknown"
    re.compile(r"\b(why|how)\b[^.?!\n]{0,80}\b(fail\w*|error\w*|broken|not working)", re.IGNORECASE),
    # Contributor activity: "user replied", "new comment on 227"
    re.compile(r"\b(replied|new comment|posted (a|an|their) )", re.IGNORECASE),
    # "look at issue 215", "read issue #227", "gather info related to issue 226"
    re.compile(r"\b(issue|pr)\s*#?\d+", re.IGNORECASE),
)

_REMINDER = (
    "If this prompt carries a log, an error, a bug report, an issue to look at or a "
    "contributor reply, invoke the diagnose-user-report skill before replying "
    "(CLAUDE.md § Diagnosis Discipline). Skip it if the skill is already loaded in "
    "this session or the prompt is none of those."
)


def main() -> None:
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except (ValueError, AttributeError):
        return
    if any(p.search(prompt) for p in _PATTERNS):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": _REMINDER}}))


if __name__ == "__main__":
    main()
