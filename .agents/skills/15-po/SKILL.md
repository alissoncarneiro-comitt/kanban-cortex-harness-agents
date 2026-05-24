---
name: a-po
description: >-
  Agent Harness PO fast-track — prompt to requirements, design, tasks with human gates.
  Use when user invokes /a-po "prompt" and scope is already clear.
aliases: ["/a-po", "/a-po prompt"]
triggers: ["user", "model"]
---

# PO — Product Owner (Fast-Track)

> **Papel**: Product Owner + Orquestrador de Spec.
> **Quando usar**: Você **já sabe** o que construir — não precisa de discovery/estudo.
> **Quando NÃO usar**: Escopo vago ou incerto → use `/a-discover` (modo estudo).

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`
- Prompt do usuário salvo em `.agents/kanban/in-progress/{ITEM}/raw-request.md`

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `brief.md` ou artefatos de `/a-discover` — este caminho parte do prompt direto, não de discovery

### Validação de pré-requisitos
Se o prompt não foi fornecido como argumento de `/a-po "..."`:
→ Interromper: "Forneça o prompt: `/a-po \"descrição do que construir\"`"

### Handoff de entrada
Usuário → este skill via `/a-po "prompt"` direto

### Handoff para Próxima Fase
Ao final, o artefato `requirements.md` deve conter:
- Todos os requisitos EARS com ACs testáveis
- Seção `## Handoff para Próxima Fase → a-spec (design)` descrevendo o que a fase de design deve ler

## Dois Caminhos de Entrada

| Situação | Comando | Resultado |
|----------|---------|-----------|
| Ainda estamos **estudando** a ideia | `/a-discover` | brief.md, WSJF, stakeholder map |
| **Já sabemos** o que queremos | `/a-po "prompt"` | requirements → design → tasks (com gates) |

## Pré-requisitos

- Projeto inicializado via `/a-steering init`
- Ler `.agents/steering/product.md` e `.agents/steering/tech.md`

## Workflow (`/a-po "seu prompt aqui"`)

### 0. Setup do item

```bash
# Criar diretório do item (gerar ITEM-XXX sequencial)
mkdir -p .agents/kanban/in-progress/ITEM-XXX/
```

Salvar prompt original em `raw-request.md`.

### Fase 1 — Requirements (PO)

Gerar `requirements.md` em formato EARS a partir do prompt:

- Functional + Non-Functional
- Given-When-Then por requisito
- Acceptance criteria testáveis
- Sem implementação técnica ainda

**PARAR. Human gate obrigatório:**

```
⏸️ Aprovação humana necessária para requirements.md
→ Responda: aprovar | ajustar [feedback] | rejeitar
→ Ou: /a-steering approve requirements ITEM-XXX
```

Não avance sem aprovação explícita.

### Fase 2 — Design (delega papel Spec/Architect)

Após requirements aprovados, executar lógica de `/a-spec` (somente design):

- `design.md` com File Structure Plan, diagrams, failure modes
- Tag `[LOCKED — approved YYYY-MM-DD]` somente após gate humano

**PARAR. Human gate obrigatório:**

```
⏸️ Aprovação humana necessária para design.md
→ /a-steering approve design ITEM-XXX
```

### Fase 3 — Tasks (delega papel Spec/Architect)

Após design aprovado e locked:

- `tasks.md` com `_Boundary:_` e `_Depends:_` em cada task
- Estimativas e acceptance criteria por task

**PARAR. Human gate obrigatório:**

```
⏸️ Aprovação humana necessária para tasks.md
→ /a-steering approve tasks ITEM-XXX
```

### Fase 4 — UI (se aplicável)

Se a feature tem interface:

```
→ /a-design ITEM-XXX
→ Human gate antes de build
```

Se **sem UI**: pular para Fase 5.

### Fase 5 — Pronto para Build

Após todos os gates:

```
✅ Item pronto para /a-plan → /a-build
```

Registrar em `task.yaml`:

```yaml
id: "ITEM-XXX"
source: "po-fast-track"
gates:
  requirements: { approved: true, approved_by: human, date: "YYYY-MM-DD" }
  design:       { approved: true, approved_by: human, date: "YYYY-MM-DD" }
  tasks:        { approved: true, approved_by: human, date: "YYYY-MM-DD" }
phases:
  po:      { done: true }
  spec:    { done: true }
  build:   { done: false }
```

## Regras de Ouro

- NUNCA pule human gate entre fases
- NUNCA gere código neste skill (isso é `/a-build`)
- NUNCA faça discovery/reframe (isso é `/a-discover`)
- SEMPRE pare e peça aprovação após requirements, design e tasks
- Se escopo ficar vago durante o PO → redirecionar para `/a-discover`

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| `/a-po "implementar pagamentos PIX"` | requirements.md → design.md → tasks.md (cada um com gate) |

**Paths**: `.agents/kanban/in-progress/{ITEM}/`

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
