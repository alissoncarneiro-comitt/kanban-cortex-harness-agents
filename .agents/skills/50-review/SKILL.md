---
name: a-review
description: >-
  Agent Harness code review — boundaries, failure modes, cross-model second opinion.
  Use when user invokes /a-review or /a-code-review after build.
aliases: ["/a-review", "/a-code-review"]
triggers: ["user", "model"]
---

# Review — Revisão Independente

> **Papel**: Staff Engineer (+ Codex second opinion se habilitado).
> **Referências**: cc-sdd independent reviewer | gstack `/review`, `/codex` | Kanban coluna Review (WIP=4)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.
> **O valor do review depende de você não ter visto o raciocínio do builder.**

### Artefatos obrigatórios — ler NESTA ORDEM
1. `.agents/kanban/in-progress/{ITEM}/design.md` (status: LOCKED) — entenda a arquitetura esperada
2. `.agents/kanban/in-progress/{ITEM}/tasks.md` (status: APPROVED) — entenda os boundaries de cada task
3. Diff do código: `git diff main..feature/{ITEM}` — apenas depois de ter formado hipótese de failure modes

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `Implementation Notes` em `tasks.md` — **não leia antes de examinar o código**; evita viés de confirmação
- `review-report.md` de iterações anteriores — forme opinião própria
- `requirements.md` e `brief.md` — o reviewer avalia contra a spec (design.md), não contra a intenção original

### Protocolo de independência
**Antes de ler o código:**
1. Leia `design.md` inteiro
2. Liste por escrito os 3-5 failure modes que você antecipa baseado na spec
3. Identifique os boundaries críticos de cada task no `tasks.md`
**Depois, ao ler o código:**
4. Verifique se seus failure modes antecipados estão cobertos
5. Procure boundary violations (prioridade máxima)
6. Apenas então leia `## Implementation Notes` para contexto adicional

### Validação de pré-requisitos
Se `design.md` não tiver `[LOCKED` ou não houver commit no branch `feature/{ITEM}`:
→ Interromper: "Build não completo. Execute `/a-build {ITEM}` primeiro."

### Handoff de entrada
`a-build` → este skill via código commitado em `feature/{ITEM}` + `tasks.md` atualizado

## Pré-requisitos

- Build completo para a task/feature
- **Contexto limpo**: ler design.md + tasks.md **antes** do código, nesta ordem

## Workflow

### 0. Board Health (obrigatório — REQ-002)

```bash
python3 scripts/board-validate.py --item {ITEM_ID}
```

- Exit ≠ 0 → interromper review; seguir `docs/how-to/recover-board-state.md`
- Exit 0 → prosseguir (WARN em órfãos não bloqueia `--item`)

### 1. Boundary Check (cc-sdd)

```bash
python .agents/skills/50-review/scripts/boundary-checker.py \
  --tasks .agents/kanban/in-progress/{ITEM}/tasks.md --diff HEAD~1
```

Violations de boundary > style issues. Sempre rejeitar drive-by edits.

### 2. Production Failure Modes

Para cada entidade/API:
- [ ] Downstream cai?
- [ ] 10x tráfego?
- [ ] DB lento?
- [ ] Input malicioso?
- [ ] Requests duplicados simultâneos?
- [ ] Deploy parcial falha?

### 3. Cross-Model (opcional)

```bash
/codex review --branch feature/{ITEM} --mode adversarial
```

### 4. Relatório

```bash
python .agents/skills/50-review/scripts/review-report-gen.py \
  --feature {ITEM} \
  --output .agents/kanban/in-progress/{ITEM}/review-report.md
```

### Decisão

- **APPROVE** → `/a-test`
- **REQUEST CHANGES** → builder corrige (ver `review-feedback.md` abaixo)
- **REJECT 2x** → auto-debug

### REQUEST CHANGES — `review-feedback.md` (obrigatório)

Antes de `handoff.py --status changes_requested`, crie ou atualize:

`.agents/kanban/in-progress/{ITEM}/review-feedback.md`

Formato mínimo (resumo **acionável** — não copie o `review-report.md` inteiro):

```markdown
# Review feedback — {ITEM}

## Must fix
- [boundary/task] descrição concreta do que corrigir

## Should fix
- melhorias opcionais

## Notes
- contexto mínimo para o builder (sem histórico de chat)
```

O builder só pode ler este ficheiro quando o pipeline setar `pipeline_retry: true` no `handoff-packet.yaml` (rebuild automático).

### Audit Trail de Review (FEAT-002 TASK-004)

Ao emitir REQUEST_CHANGES ou REJECT, registrar evento antes de encerrar:

```bash
python scripts/audit_writer.py review_rejection \
  --item {ITEM_ID} \
  --phase review \
  --session "${CLAUDE_SESSION_ID:-}" \
  --rejection-count {N} \
  --escalated {true se N>=2, senão false} \
  --reason-summary "{resumo 1 linha da razão principal}"
```

## Regras de Ouro

- SEMPRE contexto limpo (spec antes de code)
- NUNCA aprove com boundary violations
- SEMPRE verifique failure modes do design.md

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| Diff + tasks.md + design.md | `review-report.md`, task.yaml `review.done` |

**Paths**: `.agents/kanban/in-progress/{ITEM}/review-report.md`

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

Ao aprovar:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase review --status approved
```

Ao solicitar mudanças:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase review --status changes_requested
```

Cada chamada a `handoff.py` atualiza `handoff-packet.yaml` (próxima fase, `artifacts_allowed`, `session_id`). Schema: `docs/reference/handoff-packet-schema.md`. Não inclua em `artifacts_allowed` entradas proibidas para review (ex.: `review-report.md` antes do diff).
