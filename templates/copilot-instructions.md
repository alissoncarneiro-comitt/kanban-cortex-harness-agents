# GitHub Copilot Instructions

Este projeto usa o **Kanban Cortex Harness Agents**.

Leia e siga `AGENTS.md` como constituição do swarm.

## Framework

Instalado globalmente em `~/.kanban-cortex-harness-agents/` — não há arquivos do framework dentro deste projeto.

## Comandos disponíveis (`/a-*`)

| Comando | Descrição |
|---|---|
| `/a-bootstrap` | Inicializa `.agents/` no projeto (primeira vez) |
| `/a-steering` | Estratégia, routing, gates de aprovação |
| `/a-discover` | Pesquisa, brief, WSJF |
| `/a-po` | Fast-track: requirements → design → tasks |
| `/a-spec` | Requirements EARS + design locked |
| `/a-design` | UI/UX, design system |
| `/a-build` | TDD RED→GREEN, 1 task/iteração |
| `/a-review` | Revisão independente, boundary check |
| `/a-test` | Browser real, OWASP, performance |
| `/a-ship` | PR, CI, deploy, docs |
| `/a-flow` | Check-in diário, gargalos |
| `/a-replenish` | Puxar backlog (WSJF) |
| `/a-reflect` | Métricas, retrospectiva |

## Estrutura do projeto

```
.agents/
  kanban/     ← Board local (não commitado)
  steering/   ← product.md, tech.md, conventions.md
  memory/
  decisions/
specs/        ← Specs aprovadas
docs/         ← Documentação Diataxis
```

## Kanban Board

```bash
python3 ~/.kanban-cortex-harness-agents/cockpit/server.py
# → http://127.0.0.1:8337
```
