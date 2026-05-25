---
name: a-spec
description: >-
  Agent Harness spec — EARS requirements, locked design.md, tasks with boundaries.
  Use when user invokes /a-spec or /a-architect after brief approval.
aliases: ["/a-spec", "/a-architect"]
triggers: ["user", "model"]
---

# Spec — Arquitetura e Contratos

> **Papel**: Tech Lead + System Architect.
> **Referências**: cc-sdd boundary-first | gstack `/plan-eng-review` | Kanban coluna Spec (WIP=3)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`
- `.agents/kanban/in-progress/{ITEM}/brief.md` (status: APPROVED) — caminho `/a-discover`
- **OU** `.agents/kanban/in-progress/{ITEM}/requirements.md` (status: APPROVED) — caminho `/a-po`

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- Qualquer artefato de features diferentes do `{ITEM}` atual

### Validação de pré-requisitos
Se `brief.md` não tiver status APPROVED e não houver `requirements.md` APPROVED:
→ Interromper: "Artefato de entrada ausente. Execute `/a-steering approve brief` ou `/a-steering approve requirements {ITEM}` primeiro."

### Handoff de entrada
`a-discover` → este skill via `brief.md` APPROVED **ou** `a-po` via `requirements.md` APPROVED

### Handoff para Próxima Fase
Ao final, `design.md` deve conter seção `## Handoff para Próxima Fase` descrevendo o que `a-build` deve ler.

## Pré-requisitos

- `brief.md` aprovado via `/a-steering approve brief` **ou** requirements via `/a-po`
- Ler `.agents/steering/tech.md` e `.agents/steering/structure.md`

## Workflow

### 1. Requirements EARS

Preencher `templates/requirements.md`:

```
## REQ-001: [Título]
**Tipo**: Functional | Non-Functional
**Given** [contexto]
**When** [ação]
**Then** [resultado]
**And** [condição adicional]
```

### 2. Design.md (LOCKED)

Preencher `templates/design.md`:

- Context Diagram (Mermaid)
- Data Flow (Sequence Diagram)
- **File Structure Plan** (obrigatório — driveia task boundaries)
- State Machine
- Error Handling Matrix / Failure Modes
- Security Considerations
- Performance Budget
- Test Strategy matrix

Após aprovação humana, adicionar tag: `[LOCKED — approved YYYY-MM-DD]`

### 3. Tasks.md (cc-sdd)

Cada task **obrigatório**:

```markdown
## TASK-NNN: [Título]
_Boundary_: [arquivos/módulos permitidos]
_Depends_: [TASK-XXX ou Nenhum]
_Estimativa_: [horas]
_Acceptance_: [critérios testáveis]
```

### 4. Integração com Beads (FEAT-017)

Após gerar e salvar `tasks.md`, sincronizar com Beads se disponível:

```bash
python scripts/beads-sync.py \
  --item {ITEM_ID} \
  --tasks .agents/kanban/in-progress/{ITEM_ID}/tasks.md \
  --task-yaml .agents/kanban/in-progress/{ITEM_ID}/task.yaml \
  --harness harness.yaml
```

O script verifica `integrations.beads.enabled` em `harness.yaml`. Se `true` e `bd` estiver disponível:
- Cria uma issue no Beads por `TASK-NNN` encontrada em `tasks.md` (`bd q "..."`)
- Salva o `bd_id` de cada task em `task.yaml` sob `beads.tasks.{TASK_ID}.bd_id`
- Linka dependências via `bd dep add`

Se Beads não estiver habilitado ou `bd` não estiver no PATH, o script sai silenciosamente (exit 0).
`tasks.md` é gerado normalmente — Beads é complementar, não substituto.

### 5. ADRs (se necessário)

```bash
python .agents/skills/20-spec/scripts/adr-generator.py \
  --title "..." --context "..." --decision "..." --consequences "..."
```

## Regras de Ouro

- **Boundary-first**: File Structure Plan define limites entre tasks
- **Test Matrix**: cada requisito → caso de teste
- **No implementation details**: interfaces, não algoritmos internos
- **Design locked**: imutável após approve — mudança = novo `/a-discover` ou `/a-po`
- **Human gate**: `/a-steering approve design` antes de `/a-build`

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| brief.md aprovado | `requirements.md`, `design.md` [LOCKED], `tasks.md`, `adr-*.md` |

**Paths**: `.agents/kanban/in-progress/{ITEM}/` (ou backlog até puxado)

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
