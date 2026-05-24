# AGENTS.md — Constituição do Swarm

> Constituição do projeto. Detalhes operacionais em `.agents/skills/` (progressive disclosure).
> Comandos do framework usam namespace **`a-`**: **`/a-*`** no Claude Code e Cursor; **`$a-*`** no Codex CLI (ver `docs/how-to/codex-cli.md`).

## Identidade do Projeto

- **Nome**: Agent Harness Engineering Kanban
- **Stack**: Python (scripts), Shell, YAML (config) — sem frontend web
- **Padrão Arquitetural**: Skills como módulos independentes + YAML como contrato + Python scripts para orquestração
- **Linguagem Primária**: pt-BR

## Fase 0 — Obrigatória

**Projeto não inicializado?** Execute `/a-steering init` antes de qualquer outro comando.

Memória persistente: `.agents/steering/`

## Dois Caminhos de Entrada

| Situação | Comando | O que faz |
|----------|---------|-----------|
| **Estamos estudando** a ideia (escopo vago) | `/a-discover` | Brief, WSJF, stakeholder map → gates humanos |
| **Já sabemos** o que queremos (prompt claro) | `/a-po "prompt"` | Requirements → design → tasks → gate humano em **cada fase** |

Depois de spec completo: `/a-design` (se UI) → `/a-plan` → `/a-build` → `/a-review` → `/a-test` → `/a-ship`

## Regras Globais (Non-Negotiable)

1. **Spec-Driven**: Nenhum código sem `design.md` aprovado. Entrada via `/a-discover` (brief) ou `/a-po` (requirements direto).
2. **Design Locked**: Após approve, `design.md` é imutável. Mudança = novo ciclo `/a-discover` ou `/a-po`.
3. **Boundary First**: Todo `tasks.md` declara `_Boundary:_` e `_Depends:_` por task.
4. **TDD Obrigatório**: RED → GREEN → REFACTOR.
5. **1 Task por Iteração**: Engineer → commit → reviewer → próxima task.
6. **WIP Limits**: Máximo 3 itens por agente, 10 total.
7. **Safety**: `/careful`, `/freeze`, `/guard` (gstack — sem prefixo `/a-`).
8. **No Scope Creep**: Mudanças durante build voltam ao backlog.
9. **Code is Truth**: Specs guiam; código testado é a verdade.
10. **Human Gate**: Humanos aprovam **cada fase** via `/a-steering approve`:
    - Fluxo PO: requirements → design → tasks → ship
    - Fluxo Discover: brief → design → ship

## Routing de Skills

| Contexto | Comando |
|----------|---------|
| Bootstrap do projeto | `/a-steering init` |
| Próximo passo | `/a-steering route` |
| Aprovar fase (human gate) | `/a-steering approve [requirements\|brief\|design\|tasks\|ship]` |
| Estudar ideia (escopo vago) | `/a-discover` |
| Prompt direto (já sabemos) | `/a-po "prompt"` |
| Spec técnico (após brief) | `/a-spec` |
| UI/UX | `/a-design` |
| Planejar execução | `/a-plan` |
| Implementar TDD | `/a-build` |
| Revisar | `/a-review` |
| Testar QA | `/a-test` |
| Entregar | `/a-ship` |
| Reabastecer Kanban | `/a-replenish` |
| Daily flow | `/a-flow` |
| Retrospectiva | `/a-reflect` |

Skills: `.agents/skills/00-steering` … `15-po` … `80-governance`

## Comunicação entre Agentes

- Agentes **NUNCA** editam artefatos de outro papel sem permissão.
- Estado compartilhado: `.agents/kanban/board.yaml` + artefatos no filesystem.
- Decisões: `decisions/` + `.agents/steering/decision-log.md`
- Aprendizados: `.agents/memory/learnings/` via `/a-reflect`

## Formato de Commits

```
[FEATURE-XXX] <tipo>: descrição

[harness-context]
- Decisão: [o que foi decidido]
- Próximo: [o que falta]
- Bloqueio: [se houver impedimento]
```

## Multi-Plataforma

`./setup.sh --all` | `docs/reference/agent-adapters.md`

## Board Online

O cockpit é iniciado de forma idempotente no começo dos skills por `scripts/cockpit/check.py`.
Painel local padrão: `http://127.0.0.1:8337`.

## Learned User Preferences

- Comandos do framework devem sempre usar prefixo `/a-` (ex.: `/a-steering`, `/a-discover`); não usar aliases sem prefixo.
- Escopo vago ou em estudo → `/a-discover`; escopo claro → `/a-po "prompt"` com gate humano em requirements, design e tasks.
- Trabalho no Kanban deve seguir o padrão `/a-*` (skills isolados, human gates, uma fase/skill por sessão quando aplicável).
- Invocar `/a-steering approve` ou `/a-ship` no chat não basta — gates humanos precisam ser persistidos em `task.yaml`, `decision-log.md` e `board.yaml`; `/a-ship` exige `qa-report.md` PASSED e `gates.ship.approved: true`.
- Pedidos em lote (build/review/test de vários FEATs ou tasks) devem respeitar `_Depends:_` em `tasks.md` e paralelizar só o que não tiver interdependência (inclui FEATs distintos sem dependência entre si).
- Setup por plataforma: `./setup.sh --claude` ou `--cursor` (invocação `/a-*`); `./setup.sh --codex` (invocação `$a-*` no Codex CLI); `./setup.sh --all` cobre todas.
- Quando o usuário diz "codex", refere-se ao **Codex CLI** (OpenAI), não ao second opinion gstack (`codex review`) nem ao layout legado `~/.codex/skills/harness/`.
- Mudanças de produto seguem o fluxo spec-driven completo (`/a-spec` com requirements, design, tasks e rastreabilidade); setup ou doc isolados não substituem spec e gates humanos antes de `/a-build`.

## Learned Workspace Facts

- Fonte canônica de skills: `.agents/skills/`; o diretório `skills/` na raiz está deprecated (espelho legado).
- Framework sintetiza cc-sdd (spec-driven + steering), gstack (QA/review) e Kanban Ágil (WIP + gates humanos).
- `board.yaml` desincroniza com pastas `in-progress/` e `done/` (itens órfãos no backlog); `/a-flow` detecta; FEAT-004 tratará recovery.
- Workspace pode não ter `.git` — ship local (ship-log + move para `done/`) é válido sem PR/CI real.
- Mapa de invocação: `/a-*` (Claude Code, Cursor), `$a-*` (Codex CLI); guia em `docs/how-to/codex-cli.md`. `./setup.sh --all` cobre Claude, Cursor, Codex, Copilot e Devin.
- Codex CLI instala skills **flat** em `~/.codex/skills/a-*` (symlink de `.agents/skills/`); layout legado `harness/00-steering` não expõe `$a-*` no picker — `./setup.sh --codex` remove `harness/` e recria `a-*`.
- Pipeline automático (`scripts/orchestrator/pipeline.py`, FEAT-007) hoje só invoca `claude -p`; em Cursor/Codex CLI as fases pós-`approve tasks` costumam ser manuais (`/a-*` ou `$a-*`) até adapters no FEAT-011.
- Skills de fase (`/a-build`, `/a-review`, `/a-ship`, etc.) exigem sessão nova do agente e leitura só dos artefatos listados no skill — sem histórico de conversa.
