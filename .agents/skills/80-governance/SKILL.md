---
name: a-governance
description: >-
  Agent Harness Kanban governance — replenish, flow, reflect, plan, WIP metrics.
  Use when user invokes /a-governance, /a-replenish, /a-flow, /a-reflect, or /a-plan.
aliases: ["/a-governance", "/a-kanban", "/a-replenish", "/a-flow", "/a-reflect", "/a-plan", "/a-daily-flow", "/a-retrospective"]
triggers: ["user", "model"]
---

# Governance — Kanban e Melhoria Contínua

> **Papel**: Agile Master + Eng Manager + Knowledge Manager.
> **Referências**: Kanban Ágil (Alura) 3 cerimônias | gstack `/retro`, `/learn`

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Cada cerimônia deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de sessões de cerimônias anteriores.
> Leia apenas os artefatos listados abaixo para cada cerimônia.

### `/a-replenish` — Artefatos obrigatórios
- `.agents/kanban/board.yaml` (WIP limits, slots livres)
- `.agents/kanban/backlog/` (lista de itens com WSJF score)
- `.agents/steering/product.md` (prioridades de produto)

### `/a-flow` — Artefatos obrigatórios
- `.agents/kanban/board.yaml` (estado atual do quadro)
- `.agents/kanban/daily-logs/` (últimos 2 logs para comparação de tendência)
- `.agents/kanban/in-progress/` (itens em andamento — timestamps de última atividade)

### `/a-reflect` — Artefatos obrigatórios
- `.agents/kanban/board.yaml` (métricas configuradas)
- `.agents/kanban/done/` (últimos 5 itens concluídos — lead time, cycle time)
- `.agents/kanban/reviews/` (reviews anteriores — para comparação de tendência)

### `/a-plan` — Artefatos obrigatórios
- `.agents/kanban/board.yaml` (WIP limits e slots disponíveis)
- `.agents/kanban/in-progress/{ITEM}/design.md` (status: LOCKED)
- `.agents/kanban/in-progress/{ITEM}/tasks.md` (status: APPROVED)
- `.agents/kanban/in-progress/{ITEM}/task.yaml` (estado atual do item)

### Artefatos proibidos (todas as cerimônias)
- Histórico de conversa desta ou de sessões anteriores
- Artefatos de features específicas (brief.md, design.md, etc.) — cerimônias operam no nível do quadro, não de features individuais

### Validação de pré-requisitos
Se `.agents/kanban/board.yaml` não existir:
→ Interromper: "Board não inicializado. Execute `python3 scripts/init-board.py` primeiro."

## Cerimônias Kanban (Alura)

| Cerimônia | Comando | Quando | Propósito |
|-----------|---------|--------|-----------|
| Replenishment | `/a-replenish` | WIP slots livres | Puxar do backlog (WSJF) |
| Daily Flow | `/a-flow` | Diário ou item > 4h parado | Gargalos, impedimentos |
| Service Delivery Review | `/a-reflect` | 5 itens done ou quinzenal | Métricas, CFD, ações |

---

## `/a-replenish` — Replenishment Meeting

### 1. Capacity Check

```bash
python .agents/cerimonias/replenishment/scripts/capacity-planner.py
```

- WIP total vs limite (10)
- Slots livres por coluna (`.agents/kanban/board.yaml`)

### 2. Priorização WSJF

```bash
python .agents/cerimonias/replenishment/scripts/wsjf-prioritizer.py
```

### 3. Pull

- Mover item de `backlog/` → `in-progress/`
- Criar `task.yaml` com owner, reviewer, tester independentes
- **Nunca exceder WIP limits**

### Saída

- `.agents/kanban/replenishment-log.md`
- Itens em `.agents/kanban/in-progress/`

---

## `/a-flow` — Daily Flow Meeting

### 0. Board Health (obrigatório)

```bash
python scripts/board-validate.py --full
```

- Exit 1 → interromper cerimônia; seguir `docs/how-to/recover-board-state.md`
- Exit 0 → prosseguir (WARN em órfãos não bloqueia)

### 1. Bottleneck Detection

```bash
python .agents/cerimonias/daily-flow/scripts/bottleneck-detector.py
```

- > 4h sem atividade → alerta
- > 8h → blocked → escalar `/a-steering`

### 2. Actions

- Rebalancear ownership entre agents
- Registrar impedimentos
- Máximo 15 minutos — action-oriented, no blame

### Saída

- `.agents/kanban/daily-logs/YYYY-MM-DD.md`

---

## `/a-reflect` — Service Delivery Review

### 0. Board Health (obrigatório)

```bash
python scripts/board-validate.py --full
```

- Exit 1 → interromper retrospectiva até recovery documentado
- Relatório: `.agents/kanban/board-health.md`

### 1. Métricas de Fluxo

```bash
python .agents/cerimonias/service-delivery-review/scripts/metrics-collector.py
```

- Lead Time (meta: < 120h)
- Cycle Time (meta: < 72h)
- Throughput (meta: 5/semana)
- Flow Efficiency (meta: > 40%)

### 2. Token & Context Metrics (FEAT-002)

Para cada item concluído, coletar métricas de agente:

```bash
python scripts/metrics_collector.py --item {ITEM_ID} --out .agents/kanban/metrics/
```

Exibir seção **Token & Context Metrics**:

```markdown
## Token & Context Metrics — {ITEM_ID}

| Fase | tokens_input | tokens_output | efficiency | cache_hit_rate | context_pct_max |
|------|-------------|---------------|------------|----------------|-----------------|
| discover | X | Y | Y/X | Z% | W% |
| spec     | … | … | …  | …  | …  |
| build    | … | … | …  | …  | …  |

**Modelo mais eficiente por fase**: {modelo com maior token_efficiency}
**Alerta**: 🔴 se context_pct_max > 80% em qualquer fase
```

### 3. Lead Time por Fase (FEAT-002)

```markdown
## Lead Time por Fase — {ITEM_ID}

| Fase | Cycle Time | Queue Time |
|------|-----------|------------|
| discover | Xh | — |
| spec     | Xh | Qh |
| build    | Xh | Qh |

Lead Time Total: Xh | Flow Efficiency: Y%
```

Dados lidos de `.agents/kanban/metrics/lead-time.yaml` (gerado por `metrics_collector.py`).

### 4. Retrospectiva

- O que funcionou / travou?
- Máximo 3 action items com owner
- Atualizar `.agents/memory/learnings/project-patterns.md`

### Saída

- `.agents/kanban/reviews/review-YYYY-MM.md`
- Learnings propagados para swarm

---

## `/a-plan` — Planejamento de Execução

Quando design locked e item pronto para Build:

### 1. Capacidade

Verificar WIP e slots via capacity-planner

### 2. Alocação (task.yaml)

```yaml
id: "FEATURE-XXX"
owner: "agent-build"
reviewer: "agent-review"    # INDEPENDENTE do builder
tester: "agent-test"
phases:
  spec:    { done: true, approved_by: steering }
  build:   { done: false }
metrics:
  lead_time_start: "YYYY-MM-DD"
```

### 3. Sprint Kickoff (opcional)

- Revisar boundaries com builder
- Confirmar Definition of Done

---

## Regras de Ouro

- NUNCA exceda WIP limits (3/agente, 10 total)
- NUNCA ignore item blocked > 8h
- SEMPRE aloque reviewer **independente** do builder
- SEMPRE documente em `decision-log.md` quando escalar para Steering

## Entrada / Saída

| Cerimônia | Saída principal |
|-----------|-----------------|
| replenish | in-progress/ + replenishment-log |
| flow | daily-logs/ |
| reflect | reviews/ + learnings |
| plan | task.yaml atualizado |

**Board canônico**: `.agents/kanban/board.yaml`

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
