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
- `review-report.md` — **sempre** proibido na primeira passagem e em retry (use `review-feedback.md` no retry)
- `review-feedback.md` — proibido **exceto** quando `handoff-packet.yaml` tiver `pipeline_retry: true`

### Retry após review (`pipeline_retry`)

Antes de carregar artefatos, leia `.agents/kanban/in-progress/{ITEM}/handoff-packet.yaml`:

| `pipeline_retry` | Pode ler |
|------------------|----------|
| `false` ou ausente | `design.md`, `tasks.md`, `conventions.md` apenas |
| `true` | Acima + `review-feedback.md` (resumo acionável do review) |

Nunca leia `review-report.md` no build — o reviewer gera `review-feedback.md` em `REQUEST CHANGES`.

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

## Modo orquestrador vs agente manual

O pipeline (`scripts/orchestrator/pipeline.py`) e o invocador manual (`/a-build`) compartilham este skill, mas **regras de escopo e paralelismo diferem**.

### Modo orquestrador (pipeline + DAG)

Ativo quando `task_dag.enabled: true` em `.agents/config/pipeline.yaml` e o adapter invoca o skill com escopo de task.

**Como detectar**: o prompt de invocação termina com linhas explícitas (adapters Claude/Cursor):

```
ITEM={ITEM_ID}
TASK=TASK-NNN
```

(Opcionalmente o mesmo par pode aparecer em variáveis de ambiente documentadas pelo projeto; o contrato canônico do pipeline é `ITEM` + `TASK` no prompt.)

| Regra | Comportamento |
|-------|----------------|
| Uma task por invocação | Implemente **somente** a `TASK-NNN` indicada — leia `_Boundary:_` e `_Depends:_` só dessa seção em `tasks.md` |
| Paralelismo | O orquestrador pode rodar até `max_parallel_tasks` builds em **worktrees** distintos; **não** tente segunda task na mesma invocação |
| Fase build inteira | **Não** chame `handoff.py --phase build --status done` — o pipeline só marca `phase_status.build=done` após merge na branch de integração |
| Handoff por task | Ao concluir a task (testes verdes no boundary), registre progresso para o poll do pipeline |

```bash
python scripts/orchestrator/handoff.py \
  --item {ITEM_ID} \
  --phase build \
  --task {TASK_ID} \
  --status done
```

Isso atualiza `task_progress.{TASK_ID}` em `task.yaml` **sem** fechar a fase build. Em falha bloqueante, use `--status failed` com o mesmo `--task`.

Consulte `docs/explanation/task-dag-orchestration.md` para DAG, worktrees e isolamento.

### Modo agente manual (`/a-build` no chat)

Sem `TASK=` no escopo da sessão: escolha **uma** task pendente em `tasks.md` (respeitando `_Depends:_`), implemente até os critérios de aceite, atualize Implementation Notes e pare.

- **Não** assuma que outra task está em progresso no mesmo workspace.
- Handoff de fase (`--phase build --status done`) só quando **todas** as tasks de build do item estiverem concluídas **e** o humano/pipeline esperar encerramento da fase — em execução manual isolada de uma task, prefira apenas notas em `tasks.md` (sem fechar fase build prematuramente se o item ainda tem tasks pendentes).

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
- **Uma task por invocação** — no modo orquestrador, só a `TASK-NNN` do prompt; no modo manual, só a task que você escolheu para esta sessão
- **Paralelismo**: proibido para o **agente manual** no mesmo workspace (duas tasks abertas na mesma árvore). O **orquestrador** pode paralelizar tasks em worktrees separados — cada subprocesso do adapter ainda recebe uma única `TASK=`
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

### Por task (modo orquestrador — obrigatório quando `TASK=` no prompt)

Ao finalizar **esta** task com sucesso:

```bash
python scripts/orchestrator/handoff.py \
  --item {ITEM} \
  --phase build \
  --task {TASK_ID} \
  --status done
```

Ao falhar de forma irrecuperável na mesma task:

```bash
python scripts/orchestrator/handoff.py \
  --item {ITEM} \
  --phase build \
  --task {TASK_ID} \
  --status failed
```

O pipeline aguarda `task_progress.{TASK_ID}` via poll; **não** define `phase_status.build=done` neste handoff (defer até merge de todas as tasks).

### Fase build completa (modo legado ou após última task + merge)

Somente quando **todo** o escopo de build do item estiver concluído (build único sem DAG, ou orquestrador já fez merge):

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase build --status done
```

Falha global da fase:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase build --status failed
```

`--task TASK-NNN` preenche `from_task` no `handoff-packet.yaml`. Cada chamada atualiza o pacote no diretório do item (`artifacts_allowed`, `session_id`, `git`, `to_phase`). Schema: `docs/reference/handoff-packet-schema.md`. Respeite apenas os artefatos listados no pacote para a fase destino.
