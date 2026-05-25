---
name: a-discover
description: >-
  Agent Harness discovery — explore vague ideas, brief, WSJF, stakeholder map.
  Use when user invokes /a-discover or scope is unclear (study mode).
aliases: ["/a-discover", "/a-strategist", "/a-research"]
triggers: ["user", "model"]
---

# Discovery — Entendendo o Problema

> **Papel**: CEO + Product Owner + Researcher.
> **Referências**: cc-sdd `kiro-discovery` | gstack `/office-hours` | Kanban Replenishment input

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- Qualquer `spec/`, `design.md`, `requirements.md` de features em andamento — não deixe features existentes influenciar a descoberta de uma nova ideia

### Validação de pré-requisitos
Se `.agents/steering/product.md` contiver placeholders:
→ Interromper: "Projeto não inicializado. Execute `/a-steering init` primeiro."

### Handoff de entrada
Usuário / stakeholder → este skill via ideia ou prompt vago

## Pré-requisitos

- Projeto inicializado via `/a-steering init`
- Ler `.agents/steering/product.md` antes de começar

## 6 Forcing Questions (gstack)

1. **What is the pain?** — Exemplos concretos, não hipóteses
2. **Who feels it?** — Persona específica
3. **How do they solve it today?** — Workaround atual
4. **Why is this urgent now?** — Time criticality
5. **What happens if we do nothing?** — Cost of delay
6. **What is the narrowest wedge?** — MVP mental

## Workflow

### 1. Quando usar Discovery vs PO

| Situação | Comando |
|----------|---------|
| Escopo **vago** — estamos estudando | `/a-discover` (este skill) |
| Escopo **claro** — já sabemos o que quer | `/a-po "prompt"` (pula discovery) |
| Multi-spec | `roadmap.md` via `templates/roadmap.md` |

### 2. Reframe

- O usuário pediu "X". O que ele realmente precisa?
- Liste 3 framings alternativos
- Recomende o mais valioso

### 3. Stakeholder Map

```bash
python .agents/skills/10-discovery/scripts/stakeholder-map.py --input "{{ideia}}"
```

### 4. Acceptance Criteria

- Formato Given-When-Then
- Mínimo 3, máximo 7
- Testáveis sem ambiguidade

### 5. WSJF

```bash
python .agents/skills/10-discovery/scripts/wsjf-calculator.py \
  --business-value [1-10] --risk-reduction [1-10] \
  --time-criticality [1-10] --job-size [horas]
```

### 6. Brief

Preencher `templates/brief.md` em `.agents/kanban/backlog/{ITEM}/brief.md`

## Regras de Ouro

- NUNCA proponha solução técnica (isso é `/a-spec`)
- NUNCA escreva código nesta fase
- SEMPRE valide premissas com dados quando possível
- **Human gate**: `/a-steering approve brief` antes de `/a-spec`

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| Ideia vaga do stakeholder | `brief.md`, `stakeholder-map.md`, `acceptance-criteria.md` |
| Multi-spec | + `roadmap.md` |

**Paths**: `.agents/kanban/backlog/{ITEM}/`

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

# FEAT-013: item em backlog → coluna discover ao iniciar discovery
python scripts/steering-gate.py --item {ITEM_ID} --gate discover-start
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
