#!/bin/bash
# Mapa canônico: pasta em .agents/skills/ → nome do skill Codex CLI ($name)
# Codex invoca skills com $name; o name deve coincidir com frontmatter `name:` e a pasta em ~/.codex/skills/
# Mesmo mapa que Claude Code (slash /a-* ↔ dollar $a-*).

# shellcheck source=scripts/claude-skill-map.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude-skill-map.sh"

CODEX_SKILL_MAP=("${CLAUDE_SKILL_MAP[@]}")
