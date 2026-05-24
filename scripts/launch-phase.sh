#!/usr/bin/env bash
# launch-phase.sh — Valida pré-requisitos e orienta o início de nova sessão por fase.
# Uso: scripts/launch-phase.sh <ITEM> <fase>
# Exemplo: scripts/launch-phase.sh FEAT-001 design

set -euo pipefail

ITEM="${1:-}"
PHASE="${2:-}"
BASE=".agents/kanban/in-progress"

if [[ -z "$ITEM" || -z "$PHASE" ]]; then
  echo "Uso: scripts/launch-phase.sh <ITEM> <fase>"
  echo "Fases disponíveis: discover, po, spec, design, build, review, test, ship"
  echo "                   replenish, flow, reflect"
  exit 1
fi

ITEM_DIR="$BASE/$ITEM"

python3 scripts/cookip/check.py 2>/dev/null || python scripts/cookip/check.py 2>/dev/null || true

if [[ ! -d "$ITEM_DIR" ]]; then
  # Tenta backlog
  if [[ -d ".agents/kanban/backlog/$ITEM" ]]; then
    echo "AVISO: $ITEM está no backlog, não em in-progress."
    echo "       Execute /a-replenish para puxar o item antes de iniciar uma fase."
    exit 1
  fi
  echo "ERRO: Item '$ITEM' não encontrado em '$BASE'."
  exit 1
fi

_check_file() {
  local file="$1"
  local label="$2"
  if [[ ! -f "$file" ]]; then
    echo "ERRO: Artefato ausente: $file"
    echo "      ($label)"
    exit 1
  fi
}

_check_approved() {
  local file="$1"
  local label="$2"
  _check_file "$file" "$label"
  if ! head -10 "$file" | grep -qiE "^>?\s*\*?\*?Status\*?\*?.*APPROVED|\[LOCKED"; then
    echo "ERRO: Artefato existe mas não está aprovado: $file"
    echo "      Procure por 'Status: APPROVED' ou '[LOCKED' no arquivo."
    exit 1
  fi
}

_schema_validate_tasks_if_enabled() {
  local file="$1"
  if [[ "${HARNESS_FEATURE_ARTIFACT_SCHEMA_VALIDATION_V1:-false}" != "true" ]]; then
    return 0
  fi
  if [[ -x "scripts/validate-tasks.py" || -f "scripts/validate-tasks.py" ]]; then
    python3 scripts/validate-tasks.py "$file"
  else
    echo "ERRO: Validator ausente: scripts/validate-tasks.py"
    exit 1
  fi
}

_print_launch() {
  local skill="$1"
  local context_files=("${@:2}")
  echo ""
  echo "✅ Pré-requisitos verificados para '$PHASE' em '$ITEM'."
  echo ""
  echo "Inicie uma NOVA sessão Claude Code e execute:"
  echo ""
  echo "  /$skill"
  echo ""
  echo "Artefatos que o skill lerá (e somente estes):"
  for f in "${context_files[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "Não carregue nenhum histórico de sessão anterior."
}

case "$PHASE" in
  discover)
    _check_file ".agents/steering/product.md" "steering inicializado"
    if grep -q "\[Nome do Produto\]" ".agents/steering/product.md" 2>/dev/null; then
      echo "ERRO: Projeto não inicializado. Execute /a-steering init primeiro."
      exit 1
    fi
    _print_launch "a-discover" \
      ".agents/steering/product.md" \
      ".agents/steering/tech.md" \
      ".agents/steering/conventions.md"
    ;;

  po)
    _check_file ".agents/steering/product.md" "steering inicializado"
    _print_launch "a-po" \
      ".agents/steering/product.md" \
      ".agents/steering/tech.md" \
      ".agents/steering/conventions.md" \
      "(prompt do usuário como argumento: /a-po \"...\")"
    ;;

  spec)
    if [[ -f "$ITEM_DIR/brief.md" ]]; then
      _check_approved "$ITEM_DIR/brief.md" "brief aprovado via /a-steering approve brief"
      _print_launch "a-spec" \
        "$ITEM_DIR/brief.md" \
        ".agents/steering/product.md" \
        ".agents/steering/tech.md" \
        ".agents/steering/conventions.md"
    elif [[ -f "$ITEM_DIR/requirements.md" ]]; then
      _check_approved "$ITEM_DIR/requirements.md" "requirements aprovado via /a-steering approve requirements"
      _print_launch "a-spec" \
        "$ITEM_DIR/requirements.md" \
        ".agents/steering/product.md" \
        ".agents/steering/tech.md" \
        ".agents/steering/conventions.md"
    else
      echo "ERRO: Nenhum artefato de entrada encontrado para 'spec'."
      echo "      Esperado: $ITEM_DIR/brief.md (APPROVED) ou $ITEM_DIR/requirements.md (APPROVED)"
      exit 1
    fi
    ;;

  design)
    _check_approved "$ITEM_DIR/requirements.md" "requirements aprovado"
    _check_approved "$ITEM_DIR/design.md" "design aprovado via /a-steering approve design"
    _print_launch "a-design" \
      "$ITEM_DIR/requirements.md" \
      "$ITEM_DIR/design.md" \
      ".agents/steering/product.md" \
      ".agents/steering/tech.md" \
      ".agents/steering/conventions.md"
    ;;

  build)
    _check_approved "$ITEM_DIR/design.md" "design.md LOCKED"
    _check_approved "$ITEM_DIR/tasks.md" "tasks aprovadas via /a-steering approve tasks"
    _schema_validate_tasks_if_enabled "$ITEM_DIR/tasks.md"
    if [[ "${PIPELINE_ENABLED:-false}" == "true" ]] && grep -q "approved: true" "$ITEM_DIR/task.yaml" 2>/dev/null; then
      python scripts/orchestrator/pipeline.py run "$ITEM" >/dev/null 2>&1 &
    fi
    _print_launch "a-build" \
      "$ITEM_DIR/design.md" \
      "$ITEM_DIR/tasks.md" \
      ".agents/steering/conventions.md"
    ;;

  review)
    _check_approved "$ITEM_DIR/design.md" "design.md LOCKED"
    _check_approved "$ITEM_DIR/tasks.md" "tasks aprovadas"
    echo ""
    echo "✅ Pré-requisitos verificados para 'review' em '$ITEM'."
    echo ""
    echo "Inicie uma NOVA sessão Claude Code e execute:"
    echo ""
    echo "  /a-review"
    echo ""
    echo "Protocolo de independência — ler NESTA ORDEM:"
    echo "  1. $ITEM_DIR/design.md  (entenda a arquitetura esperada)"
    echo "  2. $ITEM_DIR/tasks.md   (entenda os boundaries)"
    echo "  3. git diff main..feature/$ITEM  (examine o código)"
    echo "  4. $ITEM_DIR/tasks.md ## Implementation Notes  (contexto adicional)"
    echo ""
    echo "NÃO leia review-report.md de iterações anteriores antes de formar opinião própria."
    ;;

  test)
    _check_approved "$ITEM_DIR/requirements.md" "requirements aprovados"
    if [[ ! -f "$ITEM_DIR/review-report.md" ]]; then
      echo "ERRO: review-report.md ausente. Execute /a-review $ITEM primeiro."
      exit 1
    fi
    echo ""
    echo "✅ Pré-requisitos verificados para 'test' em '$ITEM'."
    echo ""
    echo "Inicie uma NOVA sessão Claude Code e execute:"
    echo ""
    echo "  /a-test"
    echo ""
    echo "Protocolo de independência — ler NESTA ORDEM:"
    echo "  1. $ITEM_DIR/requirements.md  (derive casos de teste dos ACs)"
    echo "  2. Código no branch feature/$ITEM"
    echo "  3. $ITEM_DIR/review-report.md  (somente após executar seus próprios testes)"
    echo ""
    echo "NÃO leia review-report.md antes de executar os testes — derive do requirements.md."
    ;;

  ship)
    _check_file "$ITEM_DIR/qa-report.md" "qa-report.md (verde)"
    _check_file "$ITEM_DIR/task.yaml" "task.yaml com gate ship aprovado"
    if ! grep -q "ship.*approved: true\|approved: true" "$ITEM_DIR/task.yaml" 2>/dev/null; then
      echo "ERRO: Gate de ship não aprovado em task.yaml."
      echo "      Execute /a-steering approve ship $ITEM primeiro."
      exit 1
    fi
    _print_launch "a-ship" \
      "$ITEM_DIR/qa-report.md" \
      "$ITEM_DIR/task.yaml" \
      ".agents/steering/product.md" \
      ".agents/steering/tech.md"
    ;;

  replenish|flow|reflect)
    _check_file ".agents/kanban/board.yaml" "board.yaml inicializado"
    SKILL="a-${PHASE}"
    case "$PHASE" in
      replenish)
        _print_launch "$SKILL" \
          ".agents/kanban/board.yaml" \
          ".agents/kanban/backlog/ (todos os itens)" \
          ".agents/steering/product.md"
        ;;
      flow)
        _print_launch "$SKILL" \
          ".agents/kanban/board.yaml" \
          ".agents/kanban/daily-logs/ (últimos 2)" \
          ".agents/kanban/in-progress/ (itens em andamento)"
        ;;
      reflect)
        _print_launch "$SKILL" \
          ".agents/kanban/board.yaml" \
          ".agents/kanban/done/ (últimos 5 itens)" \
          ".agents/kanban/reviews/ (reviews anteriores)"
        ;;
    esac
    ;;

  *)
    echo "ERRO: Fase desconhecida: '$PHASE'"
    echo "Fases válidas: discover, po, spec, design, build, review, test, ship, replenish, flow, reflect"
    exit 1
    ;;
esac
