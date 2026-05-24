---
name: a-ship
description: >-
  Agent Harness ship — PR, CI, canary deploy, Diataxis docs, feature flag rollout.
  Use when user invokes /a-ship or /a-deploy after QA is green.
aliases: ["/a-ship", "/a-deploy"]
triggers: ["user", "model"]
---

# Ship — Release e Entrega

> **Papel**: Release Engineer + SRE + Doc Engineer.
> **Referências**: gstack `/ship`, `/land-and-deploy`, `/canary`, `/document-release` | Kanban coluna Ship (WIP=2)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/kanban/in-progress/{ITEM}/qa-report.md` (status: verde / PASSED)
- `.agents/kanban/in-progress/{ITEM}/task.yaml` (gate ship: approved true)

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `review-report.md`, `Implementation Notes` — o shipper age sobre o código aprovado, não sobre o processo

### Validação de pré-requisitos
Se `qa-report.md` não existir ou `task.yaml` não tiver `ship: { approved: true }`:
→ Interromper: "QA não aprovado ou gate de ship ausente. Execute `/a-test {ITEM}` e depois `/a-steering approve ship {ITEM}`."

### Handoff de entrada
`a-test` → este skill via `qa-report.md` PASSED + `/a-steering approve ship`

## Pré-requisitos

- QA verde
- **`/a-steering approve ship`** (human gate obrigatório)

## Workflow

### 1. Pre-Ship Checklist

- [ ] Testes passando (unit + integration + e2e)
- [ ] Coverage ≥ 60%
- [ ] Security sem findings críticos
- [ ] Performance sem regressão > 20%
- [ ] Feature flag OFF por default
- [ ] Rollback plan documentado

### 2. PR

```bash
python .agents/skills/70-ship/scripts/pr-generator.py --item {ITEM}
```

### 3. CI Gate

```bash
python .agents/skills/70-ship/scripts/ci-gate.py --branch feature/{ITEM}
```

### 4. Deploy + Canary

```bash
python .agents/skills/70-ship/scripts/canary-monitor.py --duration 15
```

### 5. Docs (Diataxis)

```bash
python .agents/skills/70-ship/scripts/doc-update.py --item {ITEM}
```

Atualizar: `docs/tutorial/`, `docs/how-to/`, `docs/reference/`, `docs/explanation/`

### 6. Ship Log

```bash
python .agents/skills/70-ship/scripts/ship-log.py --item {ITEM}
```

Mover item para `.agents/kanban/done/{ITEM}/`

## Regras de Ouro

- NUNCA deploy sem rollback plan
- SEMPRE canary antes de 100% traffic
- SEMPRE docs antes de marcar Done
- NUNCA ignore alerta de canary

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| qa-report verde + steering approve | PR mergeado, `ship-log.md`, docs, item em done/ |

**Paths**: `.agents/kanban/in-progress/{ITEM}/ship-log.md` → `done/{ITEM}/`

## Instrumentação

> Emite eventos de audit trail para `scripts/audit_writer.py` (FEAT-002).
> Variáveis de ambiente capturadas automaticamente pelo harness se disponíveis.

### Ao iniciar este skill (phase_start)

```bash
python3 scripts/cockpit/check.py 2>/dev/null || python scripts/cockpit/check.py 2>/dev/null || true

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

Ao finalizar ship com sucesso:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase ship --status done
```

Ao finalizar ship com falha:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase ship --status failed
```
