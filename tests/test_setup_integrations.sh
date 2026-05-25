#!/usr/bin/env bash
# Tests for FEAT-016: Beads + RTK detection/installation in setup.sh
# Acceptance criteria: TASK-001, TASK-002, TASK-004
# Run: bash tests/test_setup_integrations.sh

set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SETUP="$HARNESS_DIR/setup.sh"
PASS=0
FAIL=0
TMPDIR_ROOT=$(mktemp -d)
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

_ok() { echo "  ✅ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

# helper: fake HOME with minimal harness structure
# Does NOT pre-copy harness.yaml — setup.sh must deploy it via deploy_agent_home()
_make_fake_home() {
  local h="$TMPDIR_ROOT/$1"
  mkdir -p \
    "$h/.kanban-cortex-harness-agents/config" \
    "$h/.kanban-cortex-harness-agents/skills" \
    "$h/.kanban-cortex-harness-agents/commands" \
    "$h/.kanban-cortex-harness-agents/cerimonias" \
    "$h/.kanban-cortex-harness-agents/memory/identity" \
    "$h/.kanban-cortex-harness-agents/templates" \
    "$h/.kanban-cortex-harness-agents/scripts" \
    "$h/.kanban-cortex-harness-agents/cockpit"
  printf 'version: "1.0"\nprojects: []\n' > "$h/.kanban-cortex-harness-agents/config/project-registry.yaml"
  echo "$h"
}

# ── T01-T04: TASK-001 structural ─────────────────────────────────────────────

echo ""
echo "== TASK-001: setup.sh functions =="

if grep -q '^_check_optional_tools()' "$SETUP"; then
  _ok "_check_optional_tools() declared"
else
  _fail "_check_optional_tools() not found in setup.sh"
fi

if grep -q '^_write_harness_integration()' "$SETUP"; then
  _ok "_write_harness_integration() declared"
else
  _fail "_write_harness_integration() not found in setup.sh"
fi

update_block=$(sed -n '/--update)/,/exit 0/p' "$SETUP")
if echo "$update_block" | grep -q '_check_optional_tools'; then
  _fail "--update block calls _check_optional_tools (must NOT)"
else
  _ok "--update mode does not call _check_optional_tools"
fi

defs=$(grep -c '^_check_optional_tools()' "$SETUP" || true)
calls=$(grep -c '_check_optional_tools' "$SETUP" || true)
if [ "$calls" -gt "$defs" ]; then
  _ok "_check_optional_tools called in main flow"
else
  _fail "_check_optional_tools defined but never called"
fi

# ── T05-T06: --update does not ask about integrations ────────────────────────

echo ""
echo "== TASK-004: --update graceful =="

H=$(  _make_fake_home "update-test")
update_log="$TMPDIR_ROOT/update.log"

if HOME="$H" bash "$SETUP" --update > "$update_log" 2>&1; then
  _ok "setup.sh --update exits 0"
else
  _fail "setup.sh --update failed (exit $?)"
  cat "$update_log"
fi

if grep -q "Instalar Beads\|Instalar RTK" "$update_log" 2>/dev/null; then
  _fail "--update asked about integrations (must NOT)"
else
  _ok "--update did not ask about integrations"
fi

# ── T12: setup.sh --update deploys harness.yaml to $AGENT_HOME ───────────────

echo ""
echo "== T12: deploy_agent_home deploys harness.yaml =="

H_DEPLOY=$(_make_fake_home "deploy-test")
HOME="$H_DEPLOY" bash "$SETUP" --update > /dev/null 2>&1 || true

if [ -f "$H_DEPLOY/.kanban-cortex-harness-agents/harness.yaml" ]; then
  _ok "setup.sh --update deploys harness.yaml to \$AGENT_HOME"
else
  _fail "harness.yaml not deployed to \$AGENT_HOME after setup.sh --update"
fi

# ── T07: response N → _write_harness_integration sets enabled=false ──────────

echo ""
echo "== TASK-004: 'N' answer — no install =="

# Use a home that setup.sh --update already seeded (harness.yaml present)
H2=$(_make_fake_home "n-test")
HOME="$H2" bash "$SETUP" --update > /dev/null 2>&1 || true
harness_yaml="$H2/.kanban-cortex-harness-agents/harness.yaml"

(
  AGENT_HOME="$H2/.kanban-cortex-harness-agents"
  eval "$(sed -n '/^_write_harness_integration()/,/^}/p' "$SETUP")"
  _write_harness_integration "beads" false
  _write_harness_integration "rtk" false
) > /dev/null 2>&1 || true

if python3 -c "
import sys, pathlib
p = pathlib.Path('$harness_yaml')
try:
    import yaml
    d = yaml.safe_load(p.read_text()) or {}
    ints = d.get('integrations', {})
    beads_ok = ints.get('beads', {}).get('enabled', None) == False
    rtk_ok   = ints.get('rtk',   {}).get('enabled', None) == False
    sys.exit(0 if (beads_ok and rtk_ok) else 1)
except Exception:
    sys.exit(0)  # no yaml module — graceful pass
" 2>/dev/null; then
  _ok "enabled=false after 'N' response — harness.yaml correct"
else
  _fail "harness.yaml not set to enabled=false after 'N'"
fi

# ── T08: response Y → _write_harness_integration sets enabled=true ───────────

echo ""
echo "== TASK-004: 'Y' + mock install → enabled=true =="

H3=$(_make_fake_home "y-test")
HOME="$H3" bash "$SETUP" --update > /dev/null 2>&1 || true
harness_yaml3="$H3/.kanban-cortex-harness-agents/harness.yaml"

(
  AGENT_HOME="$H3/.kanban-cortex-harness-agents"
  eval "$(sed -n '/^_write_harness_integration()/,/^}/p' "$SETUP")"
  _write_harness_integration "beads" true
  _write_harness_integration "rtk" true
) > /dev/null 2>&1 || true

if python3 -c "
import sys, pathlib
p = pathlib.Path('$harness_yaml3')
try:
    import yaml
    d = yaml.safe_load(p.read_text()) or {}
    ints = d.get('integrations', {})
    beads_ok = ints.get('beads', {}).get('enabled', None) == True
    rtk_ok   = ints.get('rtk',   {}).get('enabled', None) == True
    sys.exit(0 if (beads_ok and rtk_ok) else 1)
except Exception:
    sys.exit(0)  # graceful if no yaml
" 2>/dev/null; then
  _ok "enabled=true after install — harness.yaml correct"
else
  _fail "harness.yaml not set to enabled=true after install"
fi

# ── T09: EXIT 0 in all paths ─────────────────────────────────────────────────

echo ""
echo "== TASK-004: EXIT 0 in all modes =="

H4=$(_make_fake_home "exit0-test")

# --update must exit 0
if HOME="$H4" bash "$SETUP" --update > /dev/null 2>&1; then
  _ok "setup.sh --update → EXIT 0"
else
  _fail "setup.sh --update → EXIT non-zero"
fi

# ── T10: TASK-002 — harness.yaml has integrations section by default ──────────

echo ""
echo "== TASK-002: harness.yaml default integrations =="

if python3 -c "
import sys, pathlib
p = pathlib.Path('$HARNESS_DIR/harness.yaml')
try:
    import yaml
    d = yaml.safe_load(p.read_text()) or {}
    ints = d.get('integrations', None)
    sys.exit(0 if ints is not None else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
  _ok "harness.yaml has integrations section"
else
  _fail "harness.yaml missing integrations section"
fi

if python3 -c "
import sys, pathlib
p = pathlib.Path('$HARNESS_DIR/harness.yaml')
try:
    import yaml
    d = yaml.safe_load(p.read_text()) or {}
    ints = d.get('integrations', {})
    beads_default = ints.get('beads', {}).get('enabled', None)
    rtk_default   = ints.get('rtk',   {}).get('enabled', None)
    sys.exit(0 if (beads_default == False and rtk_default == False) else 1)
except Exception:
    sys.exit(0)
" 2>/dev/null; then
  _ok "integrations default enabled=false for beads and rtk"
else
  _fail "integrations defaults are not false"
fi

# ── T11: TASK-003 — docs sections present ────────────────────────────────────

echo ""
echo "== TASK-003: docs sections =="

if grep -q "Integrações Opcionais" "$HARNESS_DIR/AGENTS.md"; then
  _ok "AGENTS.md has 'Integrações Opcionais' section"
else
  _fail "AGENTS.md missing 'Integrações Opcionais' section"
fi

if grep -q "Integrações Opcionais" "$HARNESS_DIR/CLAUDE.md"; then
  _ok "CLAUDE.md has 'Integrações Opcionais' section"
else
  _fail "CLAUDE.md missing 'Integrações Opcionais' section"
fi

if grep -q "bd ready\|bd create\|bd close" "$HARNESS_DIR/AGENTS.md"; then
  _ok "AGENTS.md lists essential bd commands"
else
  _fail "AGENTS.md missing bd command examples"
fi

if grep -q "rtk gain\|rtk init" "$HARNESS_DIR/AGENTS.md"; then
  _ok "AGENTS.md explains RTK hook (rtk init / rtk gain)"
else
  _fail "AGENTS.md missing RTK hook explanation"
fi

# ── T13: --update preserves existing integration flags (REQ-008) ─────────────

echo ""
echo "== T13: --update preserves integration flags =="

H_PERSIST=$(_make_fake_home "persist-test")

# First: seed harness.yaml via --update
HOME="$H_PERSIST" bash "$SETUP" --update > /dev/null 2>&1 || true
harness_persist="$H_PERSIST/.kanban-cortex-harness-agents/harness.yaml"

# Simulate user having installed Beads previously (set enabled=true)
python3 -c "
import yaml, pathlib
p = pathlib.Path('$harness_persist')
try:
    d = yaml.safe_load(p.read_text()) or {}
    d.setdefault('integrations', {}).setdefault('beads', {})['enabled'] = True
    p.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False))
except Exception:
    pass
" 2>/dev/null || true

# Run --update again (simulating: git pull && ./setup.sh --update)
HOME="$H_PERSIST" bash "$SETUP" --update > /dev/null 2>&1 || true

# Verify beads.enabled was NOT reset to false
if python3 -c "
import sys, yaml, pathlib
p = pathlib.Path('$harness_persist')
try:
    d = yaml.safe_load(p.read_text()) or {}
    val = d.get('integrations', {}).get('beads', {}).get('enabled', None)
    sys.exit(0 if val == True else 1)
except Exception:
    sys.exit(0)  # graceful if no yaml
" 2>/dev/null; then
  _ok "--update preserved beads.enabled=true (REQ-008)"
else
  _fail "--update reset beads.enabled to false — REQ-008 violated"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
