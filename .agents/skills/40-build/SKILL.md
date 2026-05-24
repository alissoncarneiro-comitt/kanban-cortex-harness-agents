---
name: a-build
description: >-
  Agent Harness build — TDD RED→GREEN, one task per iteration, feature flags.
  Use when user invokes /a-build, /a-impl, or /a-engineer.
aliases: ["/a-build", "/a-impl", "/a-engineer"]
triggers: ["user", "model"]
---

# Build — Implementação TDD

> **Papel**: Feature Engineer (+ Frontend/Backend conforme task).
> **Referências**: cc-sdd `/kiro-impl` | gstack TDD | Kanban coluna Build (WIP=5)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/conventions.md`
- `.agents/kanban/in-progress/{ITEM}/design.md` (status: LOCKED)
- `.agents/kanban/in-progress/{ITEM}/tasks.md` (status: APPROVED)

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `requirements.md`, `brief.md` — o builder segue a spec, não volta às origens
- `review-report.md` de iterações anteriores — não antecipe o reviewer

### Validação de pré-requisitos
Se `design.md` não tiver `[LOCKED` ou `tasks.md` não tiver `APPROVED`:
→ Interromper: "Execute `scripts/launch-phase.sh {ITEM} build` para verificar o estado do item."

### Handoff de entrada
`a-spec` (ou `a-design` se houver UI) → este skill via `design.md` LOCKED + `tasks.md` APPROVED

### Handoff para Próxima Fase
Ao final de cada task, atualizar `## Implementation Notes` em `tasks.md`.
O reviewer (`a-review`) lê apenas `design.md` + `tasks.md` + diff — **não** lê Implementation Notes antes de formular hipóteses.

## Pré-requisitos

- `design.md` locked + `tasks.md` com boundaries
- Task dependencies (`_Depends:_`) completas
- Ler `.agents/steering/conventions.md`

## Workflow (1 task por iteração)

### 0. Board Health (obrigatório — REQ-002)

```bash
python3 scripts/board-validate.py --item {ITEM_ID}
```

- Exit ≠ 0 → interromper build; seguir `docs/how-to/recover-board-state.md`
- Exit 0 → prosseguir (WARN em órfãos não bloqueia `--item`)

### 0.1 Schema Validation (FEAT-005)

Antes de branch, RED ou qualquer edição de código:

```bash
python3 scripts/validate-tasks.py .agents/kanban/in-progress/{ITEM_ID}/tasks.md
```

- Com `HARNESS_FEATURE_ARTIFACT_SCHEMA_VALIDATION_V1=true`, `scripts/launch-phase.sh {ITEM_ID} build` executa este check e bloqueia a fase se `tasks.md` falhar.
- Sem a flag, o comportamento legado permanece compatível até `/a-ship`.

### Por task:

1. **Read**: `tasks.md` — `_Boundary:_` e `_Depends:_`
2. **Branch**: `feature/{ITEM}-TASK-NNN`
3. **RED**: teste que falha
4. **GREEN**: código mínimo
5. **REFACTOR**: limpar, testes verdes
6. **Commit**: formato `[FEATURE-XXX] tipo: desc` + `[harness-context]`
7. **Implementation Notes**: aprendizados em `## Implementation Notes` no tasks.md
8. **Handoff**: notificar reviewer independente

### Feature Flags

- Flag por task: `{feature}_taskN_v1`
- Default OFF até `/a-ship`
- Remover flag após ship completo

### Auto-Debug (cc-sdd)

Se reviewer rejeita 2x:
1. Investigador em contexto **limpo** (só design.md + logs)
2. Máximo 3 tentativas → escalar humano

### Safety

- `/careful` antes de rm, DROP, force-push
- `/freeze` durante debug de módulo
- `/guard` em produção

## Regras de Ouro

- NUNCA edite fora do `_Boundary:_` da task
- NUNCA 2 tasks simultâneas no mesmo workspace
- SEMPRE TDD: sem teste, sem merge
- SEMPRE feature flags para código novo

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| tasks.md + design.md locked | Código em `src/`, testes, tasks.md atualizado |

**Paths**: boundaries definidos em `.agents/kanban/in-progress/{ITEM}/tasks.md`

## Instrumentação

> Emite eventos de audit trail para `scripts/audit_writer.py` (FEAT-002).
> Variáveis de ambiente capturadas automaticamente pelo harness se disponíveis.

### Ao iniciar este skill (phase_start)

```bash
python3 scripts/cookip/check.py 2>/dev/null || python scripts/cookip/check.py 2>/dev/null || true

python scripts/audit_writer.py phase_start \
  --item {ITEM_ID} \
  --phase {PHASE} \
  --model "${CLAUDE_MODEL_ID:-unknown}" \
  --session "${CLAUDE_SESSION_ID:-$(python3 -c "import uuid; print(uuid.uuid4())")}" \
  --tokens-input "${CLAUDE_INPUT_TOKENS:-}" \
  --context-pct "${CLAUDE_CONTEXT_PCT:-}"
```

### Ao finalizar este skill (phase_end)

```bash
python scripts/audit_writer.py phase_end \
  --item {ITEM_ID} \
  --phase {PHASE} \
  --model "${CLAUDE_MODEL_ID:-unknown}" \
  --session "${CLAUDE_SESSION_ID:-}" \
  --tokens-input "${CLAUDE_INPUT_TOKENS:-}" \
  --tokens-output "${CLAUDE_OUTPUT_TOKENS:-}" \
  --tokens-cache-read "${CLAUDE_CACHE_READ_TOKENS:-}" \
  --tokens-cache-write "${CLAUDE_CACHE_WRITE_TOKENS:-}" \
  --context-pct "${CLAUDE_CONTEXT_PCT:-}" \
  --status {done|blocked|rejected} \
  --artifacts "{artifacts produzidos}"
```

> Fallback: se `scripts/audit_writer.py` ausente, prosseguir sem interromper o skill.

## Handoff para Pipeline

Ao finalizar build com sucesso:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase build --status done
```

Ao finalizar build com falha:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase build --status failed
```
