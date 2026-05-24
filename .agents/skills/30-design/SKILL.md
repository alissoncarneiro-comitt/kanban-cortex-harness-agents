---
name: a-design
description: >-
  Agent Harness UI/UX — design system, mockups, responsive a11y components.
  Use when user invokes /a-design and the feature has an interface.
aliases: ["/a-design", "/a-designer"]
triggers: ["user", "model"]
---

# Design — UI/UX e Componentes

> **Papel**: UI/UX Designer + Design Engineer.
> **Referências**: gstack `/design-consultation`, `/design-html` | Kanban coluna Design (WIP=2)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`
- `.agents/kanban/in-progress/{ITEM}/requirements.md` (status: APPROVED)
- `.agents/kanban/in-progress/{ITEM}/design.md` (status: LOCKED)

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- Artefatos de `/a-spec` além de `requirements.md` e `design.md` (ex: ADRs, notas internas)

### Validação de pré-requisitos
Se `design.md` não tiver tag `[LOCKED — approved`:
→ Interromper: "design.md não está locked. Execute `/a-steering approve design {ITEM}` primeiro."

### Handoff de entrada
`a-spec` → este skill via `design.md` LOCKED + `requirements.md` APPROVED

### Handoff para Próxima Fase
Ao final, `DESIGN.md` deve conter seção `## Handoff para Próxima Fase` descrevendo o que `a-build` deve ler.

## Pré-requisitos

- `design.md` locked aprovado via `/a-steering approve design`
- Feature **tem interface** (web, mobile, CLI visual)
- Se **sem UI**: pular este skill → `/a-build`

## Workflow

### 1. Design System Check

- Verificar `DESIGN.md` global do projeto
- Se não existir, criar baseado em `.agents/steering/product.md`
- Alinhar tokens com `.agents/steering/conventions.md`

### 2. Exploração (opcional)

```bash
python .agents/skills/30-design/scripts/mockup-explorer.py \
  --feature "{ITEM}" --variants 4
```

### 3. Produção

- Componentes seguindo design system
- **Responsivo**: mobile-first
- **A11y**: ARIA, keyboard nav, WCAG 2.1 AA contrast
- **Performance**: lazy load, bundle budget
- Todos os states do state machine com UI (loading, empty, error, success)

### 4. Design Review

- Auto-review contra `design.md` locked
- Verificar error states e edge cases visuais

## Regras de Ouro

- NUNCA altere escopo definido em design.md locked
- SEMPRE entregue componentes testáveis (unit + storybook quando possível)
- Commits atômicos: um por componente

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| design.md locked + requirements | `DESIGN.md`, componentes em `src/`, screenshots |

**Paths**:
- `.agents/kanban/in-progress/{ITEM}/DESIGN.md`
- `.agents/kanban/in-progress/{ITEM}/design-screenshots/`

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
