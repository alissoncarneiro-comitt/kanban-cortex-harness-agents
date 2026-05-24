#!/bin/bash
# Mapa canônico: pasta em .agents/skills/ → nome do slash command Claude Code
# Claude registra /{nome} a partir de .claude/skills/{nome}/SKILL.md

CLAUDE_SKILL_MAP=(
  "00-steering:a-steering"
  "10-discovery:a-discover"
  "15-po:a-po"
  "20-spec:a-spec"
  "30-design:a-design"
  "40-build:a-build"
  "50-review:a-review"
  "60-test:a-test"
  "70-ship:a-ship"
  "80-governance:a-governance"
)
