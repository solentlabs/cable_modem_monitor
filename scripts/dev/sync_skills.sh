#!/bin/bash
# Sync committed skills/ into .claude/skills/ so Claude Code picks them up.
# Runs on VS Code folder open via the Welcome task.
if [ -d skills ]; then
    mkdir -p .claude/skills
    cp skills/*.md .claude/skills/
fi
