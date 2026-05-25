#!/bin/bash
# Kanban Cortex Harness Agents — Global Installer
# Installs the harness globally on the machine — never inside a project.
#
# Usage:
#   ./setup.sh                    # auto-detect installed agents + install all
#   ./setup.sh --claude           # Claude Code only
#   ./setup.sh --codex            # Codex CLI only
#   ./setup.sh --cursor           # Cursor only
#   ./setup.sh --windsurf         # Windsurf only
#   ./setup.sh --devin            # Devin CLI only
#   ./setup.sh --antigravity      # Antigravity (Google Gemini) only
#   ./setup.sh --all              # All agents
#   ./setup.sh --update           # Re-sync ~/.kanban-cortex-harness-agents/ from this repo (no symlinks)
#
# After installing, run /a-bootstrap (or $a-bootstrap) inside any project.

set -e

HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_HOME="$HOME/.kanban-cortex-harness-agents"

source "$HARNESS_DIR/scripts/claude-skill-map.sh"
source "$HARNESS_DIR/scripts/codex-skill-map.sh"

# ── OS Detection ─────────────────────────────────────────────────────────────

detect_os() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "wsl"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "linux"
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "windows"
  else
    echo "unknown"
  fi
}

OS=$(detect_os)
TARGET="${1:---auto}"

echo "🔧 Kanban Cortex Harness Agents — Setup"
echo "   OS          : $OS"
echo "   HOME        : $HOME"
echo "   Agent home  : $AGENT_HOME"
echo "   Target      : $TARGET"
echo ""

# ── Step 1: Deploy canonical framework to ~/.kanban-cortex-harness-agents/ ──────────────────────────

_rsync() {
  rsync -a --delete \
    --exclude="__pycache__" --exclude="*.pyc" \
    "$1" "$2"
}

deploy_agent_home() {
  echo "📁 Deploying framework → $AGENT_HOME"

  mkdir -p \
    "$AGENT_HOME/skills" \
    "$AGENT_HOME/commands" \
    "$AGENT_HOME/cerimonias" \
    "$AGENT_HOME/memory/identity" \
    "$AGENT_HOME/config" \
    "$AGENT_HOME/templates" \
    "$AGENT_HOME/scripts" \
    "$AGENT_HOME/cockpit"

  _rsync "$HARNESS_DIR/.agents/skills/"           "$AGENT_HOME/skills/"
  _rsync "$HARNESS_DIR/.agents/commands/"         "$AGENT_HOME/commands/"
  _rsync "$HARNESS_DIR/.agents/cerimonias/"       "$AGENT_HOME/cerimonias/"
  _rsync "$HARNESS_DIR/.agents/memory/identity/"  "$AGENT_HOME/memory/identity/"
  # project-registry.yaml accumulates project registrations — never delete it on sync
  rsync -a --delete --exclude="project-registry.yaml" \
    "$HARNESS_DIR/.agents/config/" "$AGENT_HOME/config/"
  _rsync "$HARNESS_DIR/templates/"                "$AGENT_HOME/templates/"
  _rsync "$HARNESS_DIR/scripts/"                  "$AGENT_HOME/scripts/"

  # cockpit: Python backend (scripts/cockpit/) + HTML frontend (src/cockpit/)
  # deployed flat into ~/.kanban-cortex-harness-agents/cockpit/
  cp -f "$HARNESS_DIR/scripts/cockpit/server.py"   "$AGENT_HOME/cockpit/server.py"
  cp -f "$HARNESS_DIR/scripts/cockpit/check.py"    "$AGENT_HOME/cockpit/check.py"
  cp -f "$HARNESS_DIR/scripts/cockpit/__init__.py" "$AGENT_HOME/cockpit/__init__.py"
  cp -f "$HARNESS_DIR/src/cockpit/board.html"      "$AGENT_HOME/cockpit/board.html"
  cp -f "$HARNESS_DIR/src/cockpit/markdown-renderer.js" "$AGENT_HOME/cockpit/markdown-renderer.js"

  # Store harness source path for future updates
  echo "harness_dir=$HARNESS_DIR" > "$AGENT_HOME/.harness-source"

  # Initialize project registry if not exists (never overwrite — projects accumulate here)
  REGISTRY_PATH="$AGENT_HOME/config/project-registry.yaml"
  if [ ! -f "$REGISTRY_PATH" ]; then
    printf 'version: "1.0"\nprojects: []\n' > "$REGISTRY_PATH"
  fi

  echo "   ✅ $AGENT_HOME ready"
}

# ── Helpers: symlink skills into each agent's global dir ─────────────────────

_link_claude_skills() {
  local target_dir="$1"
  echo "   skills  → $target_dir"
  mkdir -p "$target_dir"

  # Remove legacy harness/ sub-layout if present
  [ -d "$target_dir/harness" ] && rm -rf "$target_dir/harness"

  for entry in "${CLAUDE_SKILL_MAP[@]}"; do
    src_name="${entry%%:*}"
    slash_name="${entry##*:}"
    src_path="$AGENT_HOME/skills/$src_name"
    dst="$target_dir/$slash_name"

    if [ ! -d "$src_path" ]; then
      echo "     ⚠️  missing: $src_name"
      continue
    fi
    [ -e "$dst" ] || [ -L "$dst" ] && rm -rf "$dst"
    ln -sf "$src_path" "$dst"
    echo "     ✅ /$slash_name"
  done
}

_link_claude_commands() {
  local target_dir="$1"
  echo "   commands → $target_dir"
  mkdir -p "$target_dir"

  for cmd in "$AGENT_HOME/commands"/*.md; do
    [ -f "$cmd" ] || continue
    name="$(basename "$cmd")"
    dst="$target_dir/$name"
    [ -e "$dst" ] && rm -f "$dst"
    ln -sf "$cmd" "$dst"
    echo "     ✅ /${name%.md}"
  done
}

_link_codex_skills() {
  local target_dir="$1"
  echo "   skills  → $target_dir"
  mkdir -p "$target_dir"

  [ -d "$target_dir/harness" ] && rm -rf "$target_dir/harness"

  for entry in "${CODEX_SKILL_MAP[@]}"; do
    src_name="${entry%%:*}"
    codex_name="${entry##*:}"
    src_path="$AGENT_HOME/skills/$src_name"
    dst="$target_dir/$codex_name"

    if [ ! -d "$src_path" ]; then
      echo "     ⚠️  missing: $src_name"
      continue
    fi
    [ -e "$dst" ] && rm -rf "$dst"
    ln -sf "$src_path" "$dst"
    echo "     ✅ \$$codex_name"
  done
}

# ── Per-agent setup ───────────────────────────────────────────────────────────

setup_claude() {
  echo ""
  echo "🤖 Claude Code"
  _link_claude_skills   "$HOME/.claude/skills"
  _link_claude_commands "$HOME/.claude/commands"
}

setup_codex() {
  echo ""
  echo "🤖 Codex CLI"
  _link_codex_skills "$HOME/.codex/skills"
}

setup_cursor() {
  echo ""
  echo "🤖 Cursor"
  _link_claude_skills "$HOME/.cursor/skills"
}

setup_windsurf() {
  echo ""
  echo "🤖 Windsurf"
  # Windsurf uses ~/.codeium/windsurf/ as global config root
  _link_claude_skills "$HOME/.codeium/windsurf/skills"
}

setup_devin() {
  echo ""
  echo "🤖 Devin CLI"
  local devin_dir
  case "$OS" in
    windows)
      devin_dir="${APPDATA}/devin/skills"
      ;;
    macos)
      devin_dir="$HOME/Library/Application Support/devin/skills"
      ;;
    *)  # linux, wsl
      devin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/devin/skills"
      ;;
  esac
  _link_claude_skills "$devin_dir"
}

setup_antigravity() {
  echo ""
  echo "🤖 Antigravity (Google Gemini)"
  _link_claude_skills "$HOME/.gemini/antigravity/skills"
}

# ── Optional integrations: Beads + RTK ───────────────────────────────────────

_write_harness_integration() {
  local tool="$1" enabled="$2"
  local harness_yaml="$AGENT_HOME/harness.yaml"
  python3 - "$harness_yaml" "$tool" "$enabled" <<'PYEOF'
import sys, pathlib
tool_name, enabled_val = sys.argv[2], sys.argv[3] == "true"
p = pathlib.Path(sys.argv[1])
try:
    import yaml
    data = yaml.safe_load(p.read_text()) or {}
    integrations = data.setdefault("integrations", {})
    integrations.setdefault(tool_name, {})["enabled"] = enabled_val
    p.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
except Exception:
    pass  # graceful: don't break setup on yaml failure
PYEOF
}

_check_optional_tools() {
  echo ""
  echo "🔌 Integrações opcionais"

  # ── Beads ──────────────────────────────────────────────────────────────────
  if command -v bd &>/dev/null; then
    echo "   ✅ Beads (bd) instalado"
    _write_harness_integration "beads" true
  else
    echo "   ℹ️  Beads — issue tracker para agentes IA: https://github.com/gastownhall/beads"
    printf "      Instalar Beads? [y/N] "
    read -r _ans
    if [[ "$_ans" =~ ^[Yy]$ ]]; then
      if curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash; then
        echo "   ✅ Beads instalado"
        _write_harness_integration "beads" true
      else
        echo "   ⚠️  Falha ao instalar Beads — instale manualmente"
        _write_harness_integration "beads" false
      fi
    else
      echo "   ⏭️  Beads ignorado"
      _write_harness_integration "beads" false
    fi
  fi

  # ── RTK ────────────────────────────────────────────────────────────────────
  if command -v rtk &>/dev/null; then
    echo "   ✅ RTK instalado"
    _write_harness_integration "rtk" true
  else
    echo "   ℹ️  RTK — proxy de tokens (60-90% economia): https://github.com/rtk-ai/rtk"
    printf "      Instalar RTK? [y/N] "
    read -r _ans
    if [[ "$_ans" =~ ^[Yy]$ ]]; then
      if curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh; then
        rtk init -g 2>/dev/null || true
        echo "   ✅ RTK instalado e configurado"
        _write_harness_integration "rtk" true
      else
        echo "   ⚠️  Falha ao instalar RTK — instale manualmente"
        _write_harness_integration "rtk" false
      fi
    else
      echo "   ⏭️  RTK ignorado"
      _write_harness_integration "rtk" false
    fi
  fi
}

# ── Auto-detect installed agents ─────────────────────────────────────────────

_run_auto_detect() {
  local agents=()

  command -v claude    &>/dev/null && agents+=("claude")
  command -v codex     &>/dev/null && agents+=("codex")
  command -v cursor    &>/dev/null && agents+=("cursor")
  command -v windsurf  &>/dev/null && agents+=("windsurf")
  command -v devin     &>/dev/null && agents+=("devin")
  [ -d "$HOME/.gemini" ] && agents+=("antigravity")

  if [ ${#agents[@]} -eq 0 ]; then
    echo "   ℹ️  No agent binaries detected — installing Claude Code + Codex CLI by default"
    agents=("claude" "codex")
  else
    echo "   🔍 Detected: ${agents[*]}"
  fi

  for agent in "${agents[@]}"; do
    case "$agent" in
      claude)      setup_claude ;;
      codex)       setup_codex ;;
      cursor)      setup_cursor ;;
      windsurf)    setup_windsurf ;;
      devin)       setup_devin ;;
      antigravity) setup_antigravity ;;
    esac
  done
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "$TARGET" in
  --help|-h)
    echo "Usage: ./setup.sh [--claude|--codex|--cursor|--windsurf|--devin|--antigravity|--all|--update]"
    echo ""
    echo "  (no args)      Auto-detect installed agents"
    echo "  --claude       Claude Code     ~/.claude/skills/ + ~/.claude/commands/"
    echo "  --codex        Codex CLI       ~/.codex/skills/"
    echo "  --cursor       Cursor          ~/.cursor/skills/"
    echo "  --windsurf     Windsurf        ~/.codeium/windsurf/skills/"
    echo "  --devin        Devin CLI       ~/.config/devin/skills/"
    echo "  --antigravity  Antigravity     ~/.gemini/antigravity/skills/"
    echo "  --all          All agents"
    echo "  --update       Re-sync ~/.kanban-cortex-harness-agents/ only (no symlinks)"
    exit 0
    ;;
  --update)
    deploy_agent_home
    echo ""
    echo "✅ ~/.kanban-cortex-harness-agents/ updated. Run ./setup.sh --all to refresh symlinks."
    exit 0
    ;;
esac

# Always deploy to ~/.kanban-cortex-harness-agents/ first
deploy_agent_home

case "$TARGET" in
  --claude)      setup_claude ;;
  --codex)       setup_codex ;;
  --cursor)      setup_cursor ;;
  --windsurf)    setup_windsurf ;;
  --devin)       setup_devin ;;
  --antigravity) setup_antigravity ;;
  --all)
    setup_claude
    setup_codex
    setup_cursor
    setup_windsurf
    setup_devin
    setup_antigravity
    ;;
  --auto|*)
    _run_auto_detect
    ;;
esac

_check_optional_tools

echo ""
echo "🎉 Setup complete!"
echo ""
echo "   Framework installed at: $AGENT_HOME"
echo ""
echo "   ▶  Initialize a project (run inside your project directory):"
echo "        Claude Code:  /a-bootstrap"
echo "        Codex CLI:    \$a-bootstrap"
echo ""
echo "   ▶  View Kanban board (after /a-bootstrap in a project):"
echo "        python3 ~/.kanban-cortex-harness-agents/cockpit/server.py"
echo ""
echo "   ▶  Update harness later:"
echo "        git -C $HARNESS_DIR pull && ./setup.sh --update"
echo ""
echo "   Constitution: $HARNESS_DIR/AGENTS.md"
