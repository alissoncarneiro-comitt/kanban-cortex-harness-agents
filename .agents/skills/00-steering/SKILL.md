---
name: a-steering
description: >-
  Agent Harness steering — bootstrap, routing, human approval gates.
  Use when user invokes /a-steering, /a-steering init, /a-steering route,
  or /a-steering approve.
aliases: ["/a-steering", "/a-steering init", "/a-steering route", "/a-steering approve", "/a-strategy"]
triggers: ["user", "model"]
---

# Steering — Comitê Estratégico (Fase 0)

> **Papel**: Steering Committee (PO + CTO + Chief Architect).
> **Comando**: sempre prefixo `/a-` (ex: `/a-steering init`)

Este skill **NÃO escreve código**. Decide **o que** construir, **por quê**, e **quando** avançar colunas do Kanban.

## Cockpit

Antes de qualquer ação, inicie o Cockpit silenciosamente se não estiver rodando:

```bash
python3 ~/.kanban-cortex-harness-agents/cockpit/check.py
```

→ http://127.0.0.1:8337

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`
- `.agents/kanban/board.yaml`

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores

### Validação de pré-requisitos
Se `.agents/steering/product.md` contiver placeholders `[Nome do Produto]`:
→ Interromper: "Projeto não inicializado. Execute `/a-steering init` primeiro."

### Handoff de entrada
Qualquer fase anterior → este skill via gate explícito (`approve brief|requirements|design|tasks|ship`)

## Modos de Operação

| Comando | Modo | Quando usar |
|---------|------|-------------|
| `/a-steering init` | **Bootstrap** | Repo novo ou placeholders em AGENTS.md |
| `/a-steering route` | **Routing** | Demanda nova, dúvida de próximo passo |
| `/a-steering approve` | **Gate** | Aprovar artefato de fase |
| `/a-steering` | **Auto** | Detecta modo pelo contexto |

### Verificação de inicialização

Projeto **não inicializado** se:
- `AGENTS.md` contém `[Nome do Produto]` ou placeholders
- `.agents/steering/product.md` não existe

→ Redirecionar para `/a-steering init` antes de qualquer fluxo.

---

## Modo A — Bootstrap (`/a-steering init`)

1. Entrevista: nome, stack, arquitetura, idioma, deploy, métrica de sucesso
2. `python scripts/init-board.py`
3. Preencher AGENTS.md, steering docs, decision-log
4. **Saída**: pronto para `/a-discover` ou `/a-po`

---

## Modo B — Routing (`/a-steering route`)

### Escolha do caminho de entrada

| Situação | Comando | Notas |
|----------|---------|-------|
| Projeto não inicializado | `/a-steering init` | Obrigatório |
| **Escopo vago — estamos estudando** | `/a-discover` | Brief, WSJF, stakeholder map |
| **Já sabemos o que queremos** | `/a-po "prompt"` | Fast-track: requirements → design → tasks |
| Requirements prontos, sem aprovação | `/a-steering approve requirements` | Human gate |
| Design pronto, sem aprovação | `/a-steering approve design` | Human gate |
| Tasks prontas, sem aprovação | `/a-steering approve tasks` | Human gate |
| Brief existe (discover path) | `/a-steering approve brief` | Human gate |
| Spec completo, tem UI | `/a-design` | Componentes |
| Spec completo, sem UI | `/a-build` | TDD |
| Build completo | `/a-review` | Review independente |
| Review ok | `/a-test` | QA + security |
| Test verde | `/a-steering approve ship` | Human gate |
| Conflito reviewer/builder | Decisão + decision-log | Escalar aqui |
| Backlog vazio | `/a-replenish` | Cerimônia Kanban |
| Item parado > 4h | `/a-flow` | Daily flow |
| 5 itens done | `/a-reflect` | Métricas |

**Comportamento**: recomendar **um** próximo comando e parar.

---

## Modo C — Gates (`/a-steering approve [tipo] [ITEM]`)

### `approve requirements` (fluxo `/a-po`)

- [ ] `requirements.md` em EARS com acceptance criteria testáveis
- [ ] Prompt original salvo em `raw-request.md`
- [ ] Sem detalhes de implementação prematuros

### `approve brief` (fluxo `/a-discover`)

- [ ] Acceptance criteria Given-When-Then (3–7)
- [ ] WSJF ou prioridade justificada
- [ ] `stakeholder-map.md` presente
- [ ] Após registrar aprovação, promover coluna no board (FEAT-013):

```bash
python scripts/steering-gate.py --item {ITEM} --gate approve-brief
# equivalente: trigger steering.approve.brief → coluna spec
```

Snippet reutilizável (qualquer gate):

```bash
python scripts/steering-gate.py --item {ITEM} --gate approve-brief   # → spec
python scripts/steering-gate.py --item {ITEM} --gate approve-tasks   # → build
python scripts/steering-gate.py --item {ITEM} --trigger steering.approve.requirements
```

Desligar sync: `BOARD_AUTO_PROMOTE=false`.

### `approve design`

- [ ] File Structure Plan completo
- [ ] Failure modes documentados
- [ ] Tag `[LOCKED — approved YYYY-MM-DD]` após aprovação

### `approve tasks`

- [ ] Cada task com `_Boundary:_` e `_Depends:_`
- [ ] Test matrix cobre requisitos
- [ ] Registrar `gates.tasks.approved = true` em `task.yaml`
- [ ] Após registrar aprovação, promover coluna no board (FEAT-013):

```bash
python scripts/steering-gate.py --item {ITEM} --gate approve-tasks
# equivalente: trigger steering.approve.tasks → coluna build
```

- [ ] Disparar pipeline em background (opt-in):

```bash
PIPELINE_ENABLED=true python scripts/orchestrator/pipeline.py run {ITEM} &
```

### `approve ship`

- [ ] QA verde, CI passando, docs Diataxis, rollback plan

Registrar em `task.yaml` e `decision-log.md`.

### Audit Trail de Aprovação (FEAT-002 TASK-004)

Após qualquer aprovação ou rejeição humana, emitir evento:

```bash
python scripts/audit_writer.py human_approval \
  --item {ITEM_ID} \
  --phase {phase_aprovada} \
  --decision approved   # ou rejected \
  --actor human \
  --session "${CLAUDE_SESSION_ID:-manual}"
```

---

## Entrada / Saída

**Paths**: `.agents/kanban/`, `.agents/steering/`, `templates/`

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

## Pipeline Integration

- `/a-steering pause {ITEM}` executa `python scripts/orchestrator/pipeline.py pause {ITEM}`.
- `/a-steering resume {ITEM}` executa `python scripts/orchestrator/pipeline.py resume {ITEM}`.
- Após **`approve tasks`**, o pipeline só dispara se `PIPELINE_ENABLED=true` ou `HARNESS_PIPELINE_ENABLED=true` (opt-in; manual por padrão).
- `scripts/launch-phase.sh {ITEM} build` imprime hint de pipeline quando essas variáveis estão ausentes.

### Gates × automático (pós-approve tasks, AC-7)

| Até | Humano | Depois de approve tasks |
|-----|--------|-------------------------|
| Spec | `approve brief\|requirements\|design\|tasks` | Build/review/test via pipeline **ou** `/a-*` manual |
| Ship | **`approve ship`** sempre | Pipeline pausa até `resume … ship` |
| Codex CLI | `$a-*` manual | Fora do registry automático |

Tabela completa: `docs/how-to/auto-orchestration.md`. Gates `approve ship` e spec **não** foram removidos.
