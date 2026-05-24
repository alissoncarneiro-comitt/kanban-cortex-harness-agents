# CLAUDE.md — Contexto do Projeto

## Sobre este Projeto

Este projeto usa o **Agent Harness Engineering Kanban**, um framework de desenvolvimento
orquestrado por agentes de IA com Kanban, Spec-Driven Development, e roles especializadas.

**Constituição completa**: [`AGENTS.md`](AGENTS.md)

> **Todos os comandos do framework usam prefixo `/a-`**

## Fase 0 — Obrigatória

Antes de qualquer trabalho: `/a-steering init` (se placeholders em AGENTS.md).

## Dois Caminhos de Entrada

| Situação | Comando |
|----------|---------|
| Escopo vago — estamos estudando | `/a-discover` |
| Escopo claro — já sabemos o que quer | `/a-po "prompt"` |

O fluxo `/a-po` gera requirements → design → tasks, com **human gate** em cada fase via `/a-steering approve`.

## Comandos Disponíveis

### Fase 0 — Steering
- `/a-steering init` — Bootstrap do projeto (AGENTS.md, steering docs, kanban)
- `/a-steering route` — Próximo comando recomendado
- `/a-steering approve` — Gates: requirements, brief, design, tasks, ship

### Pipeline Spec-Driven
- `/a-discover` — Pesquisa, brief, WSJF, stakeholder map (modo estudo)
- `/a-po "prompt"` — Fast-track PO: requirements → design → tasks (gates humanos)
- `/a-spec` — Requirements EARS, design.md locked, tasks.md (após brief)
- `/a-design` — UI/UX, design system, componentes (se houver interface)
- `/a-plan` — Capacidade, WIP, alocação de tasks
- `/a-build` — TDD RED→GREEN, 1 task/iteração, feature flags
- `/a-review` — Revisão independente, boundary check, failure modes
- `/a-test` — Browser real, OWASP, performance
- `/a-ship` — PR, CI, deploy, docs Diataxis

### Cerimônias Kanban
- `/a-replenish` — Puxar do backlog (WSJF)
- `/a-flow` — Check-in diário, gargalos
- `/a-reflect` — Métricas, CFD, retrospectiva

### Ferramentas de Segurança (gstack — sem prefixo `/a-`)
- `/careful` — Warn antes de comandos destrutivos
- `/freeze` — Lock edição em diretório
- `/guard` — `/careful` + `/freeze`

## Estrutura de Diretórios

```
.agents/
├── skills/         # Skills canônicos (00-steering … 15-po … 80-governance)
├── steering/       # Memória persistente (product, tech, conventions)
├── kanban/         # Estado do quadro
└── memory/         # Learnings e identity souls
specs/              # Specs aprovadas (active/ + archive/)
src/                # Código-fonte
tests/              # Testes
docs/               # Documentação Diataxis
kanban/             # Symlink → .agents/kanban/
```

## Referências

- `AGENTS.md` — Constituição do swarm
- `.agents/swarm.yaml` — Configuração global
- `.agents/kanban/board.yaml` — Estado do Kanban
- `docs/reference/agent-adapters.md` — Claude, Cursor, Copilot, Devin, Codex
- `specs/active/` — Specs em desenvolvimento

## Setup

```bash
./setup.sh --claude   # /a-* no Claude Code
./setup.sh --codex    # $a-* no Codex CLI
./setup.sh --all
/a-steering init
```
