#!/bin/bash
# Setup do Agent Harness Engineering Kanban
# Usage: ./setup.sh [--devin|--claude|--codex|--cursor|--copilot|--all]

set -e

HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"
CANONICAL_SKILLS="$HARNESS_DIR/.agents/skills"
AGENT="${1:---devin}"

# shellcheck source=scripts/claude-skill-map.sh
source "$HARNESS_DIR/scripts/claude-skill-map.sh"
# shellcheck source=scripts/codex-skill-map.sh
source "$HARNESS_DIR/scripts/codex-skill-map.sh"

echo "🔧 Agent Harness Engineering Kanban — Setup"
echo "   Diretório: $HARNESS_DIR"
echo "   Skills canônicos: $CANONICAL_SKILLS"
echo "   Plataforma: $AGENT"

if [ ! -d "$CANONICAL_SKILLS" ]; then
    echo "❌ .agents/skills/ não encontrado. Execute a partir da raiz do framework."
    exit 1
fi

echo ""
echo "📁 Inicializando Kanban..."
cd "$HARNESS_DIR"
python3 scripts/init-board.py

install_symlinks() {
    local target_dir="$1"
    local label="$2"

    echo ""
    echo "📦 Instalando skills → $label ($target_dir)"

    if ! mkdir -p "$target_dir" 2>/dev/null; then
        echo "   ⚠️  Pulando $label (sem permissão de escrita)"
        return 0
    fi

    for skill in "$CANONICAL_SKILLS"/*/; do
        [ -d "$skill" ] || continue
        skill_name="$(basename "$skill")"
        target_skill="$target_dir/$skill_name"

        if [ -e "$target_skill" ] || [ -L "$target_skill" ]; then
            rm -rf "$target_skill"
        fi

        ln -sf "$skill" "$target_skill"
        echo "   ✅ $skill_name"
    done
}

# Claude Code: slash = nome da pasta em .claude/skills/{nome}/ (NÃO lê aliases do frontmatter)
install_claude_skills() {
    local target_dir="$1"
    local label="$2"

    echo ""
    echo "📦 Instalando slash commands Claude → $label ($target_dir)"

    if ! mkdir -p "$target_dir" 2>/dev/null; then
        echo "   ⚠️  Pulando $label (sem permissão de escrita)"
        return 0
    fi

    # Remover layout legado harness/00-steering (registrava /harness:00-steering)
    if [ -d "$target_dir/harness" ] || [ -L "$target_dir/harness" ]; then
        rm -rf "$target_dir/harness"
        echo "   🗑️  Removido layout legado harness/"
    fi

    for entry in "${CLAUDE_SKILL_MAP[@]}"; do
        src_name="${entry%%:*}"
        slash_name="${entry##*:}"
        src_path="$CANONICAL_SKILLS/$src_name"
        target_skill="$target_dir/$slash_name"

        if [ ! -d "$src_path" ]; then
            echo "   ⚠️  Skill ausente: $src_name"
            continue
        fi

        if [ -e "$target_skill" ] || [ -L "$target_skill" ]; then
            rm -rf "$target_skill"
        fi

        ln -sf "$src_path" "$target_skill"
        echo "   ✅ /$slash_name ← $src_name"
    done
}

install_claude_commands() {
    local target_dir="$1"
    local label="$2"
    local src_commands="$HARNESS_DIR/.agents/commands"

    if [ ! -d "$src_commands" ]; then
        return 0
    fi

    echo ""
    echo "📦 Instalando commands extras → $label ($target_dir)"

    if ! mkdir -p "$target_dir" 2>/dev/null; then
        echo "   ⚠️  Pulando $label (sem permissão de escrita)"
        return 0
    fi

    for cmd in "$src_commands"/*.md; do
        [ -f "$cmd" ] || continue
        cmd_name="$(basename "$cmd")"
        target_cmd="$target_dir/$cmd_name"

        if [ "$(readlink -f "$cmd")" = "$(readlink -f "$target_cmd" 2>/dev/null || echo "")" ]; then
            echo "   ✅ /${cmd_name%.md} (canônico)"
            continue
        fi

        if [ -e "$target_cmd" ] || [ -L "$target_cmd" ]; then
            rm -f "$target_cmd"
        fi

        ln -sf "$cmd" "$target_cmd"
        echo "   ✅ /${cmd_name%.md}"
    done
}

setup_claude() {
    install_claude_skills "$HARNESS_DIR/.claude/skills" "Claude Code skills (projeto)"
    install_claude_commands "$HARNESS_DIR/.claude/commands" "Claude Code commands (projeto)"
    install_claude_skills "$HOME/.claude/skills" "Claude Code skills (global)"
    install_claude_commands "$HOME/.claude/commands" "Claude Code commands (global)"
}

# Codex CLI: skills em ~/.codex/skills/{name}/ com invocação $name (ex: $a-build)
install_codex_skills() {
    local target_dir="$1"
    local label="$2"

    echo ""
    echo "📦 Instalando skills Codex CLI → $label ($target_dir)"

    if ! mkdir -p "$target_dir" 2>/dev/null; then
        echo "   ⚠️  Pulando $label (sem permissão de escrita)"
        return 0
    fi

    # Layout legado harness/00-steering não expõe $a-* no picker do Codex
    if [ -d "$target_dir/harness" ] || [ -L "$target_dir/harness" ]; then
        if rm -rf "$target_dir/harness" 2>/dev/null; then
            echo "   🗑️  Removido layout legado harness/ (use \$a-* na raiz de skills)"
        else
            echo "   ⚠️  Não foi possível remover $target_dir/harness/ (permissão?)"
            echo "      Remova manualmente: rm -rf \"$target_dir/harness\""
        fi
    fi

    for entry in "${CODEX_SKILL_MAP[@]}"; do
        src_name="${entry%%:*}"
        codex_name="${entry##*:}"
        src_path="$CANONICAL_SKILLS/$src_name"
        target_skill="$target_dir/$codex_name"

        if [ ! -d "$src_path" ]; then
            echo "   ⚠️  Skill ausente: $src_name"
            continue
        fi

        if [ -e "$target_skill" ] || [ -L "$target_skill" ]; then
            rm -rf "$target_skill"
        fi

        ln -sf "$src_path" "$target_skill"
        echo "   ✅ \$$codex_name ← $src_name"
    done
}

setup_codex() {
    install_codex_skills "$HARNESS_DIR/.codex/skills" "Codex CLI skills (projeto)"
    install_codex_skills "$HOME/.codex/skills" "Codex CLI skills (global)"
}

validate_devin() {
    echo ""
    echo "✅ Devin: skills já no repo (.agents/skills/) — zero install extra"
    python3 scripts/validate-harness.py 2>/dev/null || echo "   ⚠️  validate-harness.py não encontrado (será criado)"
}

case "$AGENT" in
    --devin)
        validate_devin
        ;;
    --claude)
        setup_claude
        ;;
    --codex)
        setup_codex
        ;;
    --cursor)
        install_claude_skills "$HARNESS_DIR/.cursor/skills" "Cursor skills (projeto)"
        install_claude_skills "$HOME/.cursor/skills" "Cursor skills (global)"
        ;;
    --copilot)
        install_symlinks "$HARNESS_DIR/.github/skills/harness" "GitHub Copilot (projeto)"
        ;;
    --all)
        validate_devin
        setup_claude
        setup_codex
        install_claude_skills "$HARNESS_DIR/.cursor/skills" "Cursor skills (projeto)"
        install_claude_skills "$HOME/.cursor/skills" "Cursor skills (global)"
        install_symlinks "$HARNESS_DIR/.github/skills/harness" "GitHub Copilot (projeto)"
        ;;
    *)
        echo "Uso: ./setup.sh [--devin|--claude|--codex|--cursor|--copilot|--all]"
        echo ""
        echo "  --devin   Valida .agents/skills/ in-repo (padrão Devin)"
        echo "  --claude  Slash /a-* em .claude/skills/ + .claude/commands/"
        echo "  --codex   Skills \$a-* em ~/.codex/skills/ (Codex CLI)"
        echo "  --cursor  Skills /a-* em .cursor/skills/"
        echo "  --copilot Symlinks para GitHub Copilot"
        echo "  --all     Todas as plataformas"
        exit 1
        ;;
esac

echo ""
echo "🎉 Setup completo!"
echo ""
if [[ "$AGENT" == "--claude" || "$AGENT" == "--all" ]]; then
    echo "Claude Code: abra nova sessão e digite /help — deve listar /a-steering, /a-discover, /a-po, etc."
    echo ""
fi
if [[ "$AGENT" == "--codex" || "$AGENT" == "--all" ]]; then
    echo "Codex CLI: no chat interativo use \$a-steering, \$a-discover, \$a-po, etc."
    echo "           (mesmos skills que /a-* no Claude; ver docs/how-to/codex-cli.md)"
    echo ""
fi
echo "Próximos passos:"
echo "  Claude/Cursor: /a-steering init | Codex CLI: \$a-steering init"
echo "  2a. discover — /a-discover ou \$a-discover \"sua ideia\""
echo "  2b. PO       — /a-po ou \$a-po \"seu prompt\""
echo "  3. gates     — /a-steering approve … (humano; igual em todas as plataformas)"
echo "  4. pipeline  — /a-spec → /a-design → /a-build → /a-review → /a-test → /a-ship"
echo ""
echo "Constituição: AGENTS.md"
echo "Adapters:     docs/reference/agent-adapters.md"
