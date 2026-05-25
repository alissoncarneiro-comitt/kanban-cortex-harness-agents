# CLAUDE.md — Kanban Cortex Harness

## Sobre este Projeto

Template de `CLAUDE.md` para projetos que usam o **Kanban Cortex Harness Agents**.

O framework é instalado **globalmente** em `~/.kanban-cortex-harness-agents/` — o projeto fica limpo.

**Constituição completa**: [`AGENTS.md`](AGENTS.md)

> **Todos os comandos do framework usam prefixo `/a-`**

---

## Setup (uma vez por máquina)

```bash
git clone https://github.com/alissoncarneiro-comitt/kanban-cortex-harness-agents
cd kanban-cortex-harness-agents
./setup.sh          # auto-detecta agents instalados
# ou
./setup.sh --all    # Claude + Codex + Cursor + Windsurf + Devin + Antigravity
```

Regra operacional: sempre execute `git pull` dentro de `kanban-cortex-harness-agents/`.
Exemplo:

```bash
cd kanban-cortex-harness-agents
git pull origin main
./setup.sh --update
```

## Bootstrap (uma vez por projeto)

```bash
cd meu-projeto
/a-bootstrap        # Claude Code  — inicializa .agents/ no projeto
$a-bootstrap        # Codex CLI
```

---

## Comandos Disponíveis

### Bootstrap & Steering
- `/a-bootstrap` — Inicializa `.agents/` no projeto atual
- `/a-steering`  — Estratégia, decisões, routing
- `/a-steering approve` — Gates: requirements, brief, design, tasks, ship

### Pipeline Spec-Driven
- `/a-discover "ideia"` — Pesquisa, brief, WSJF, stakeholder map
- `/a-po "prompt"` — Fast-track: requirements → design → tasks
- `/a-spec`    — Requirements EARS + design.md locked + tasks.md
- `/a-design`  — UI/UX, design system, componentes
- `/a-build`   — TDD RED→GREEN, 1 task/iteração
- `/a-review`  — Revisão independente, boundary check
- `/a-test`    — Browser real, OWASP, performance
- `/a-ship`    — PR, CI, deploy, docs Diataxis

### Cerimônias Kanban
- `/a-replenish` — Puxar do backlog (WSJF)
- `/a-flow`      — Check-in diário, gargalos
- `/a-reflect`   — Métricas, CFD, retrospectiva

---

## Estrutura do Projeto (após /a-bootstrap)

```
[projeto]/
├── .agents/
│   ├── kanban/      # Board local (não versionado)
│   ├── steering/    # product.md, tech.md, conventions.md (versionado)
│   ├── memory/      # Memória dos agentes
│   ├── decisions/   # ADRs e decision log
│   └── swarm.yaml   # Config do projeto
├── specs/           # Specs aprovadas (active/ + archive/)
├── docs/            # Documentação Diataxis
├── kanban -> .agents/kanban
└── AGENTS.md
```

Framework global (não fica no projeto):
```
~/.kanban-cortex-harness-agents/
├── skills/          # 05-bootstrap … 80-governance
├── commands/
├── cerimonias/
├── cockpit/          # Kanban board UI
├── config/
└── templates/
```

---

## Board Kanban

```bash
cd meu-projeto
python3 ~/.kanban-cortex-harness-agents/cockpit/server.py
# Abre em http://127.0.0.1:8337
```

## Integrações Opcionais

| Tool | Propósito | Instalar via |
|------|-----------|--------------|
| **Beads** (`bd`) | Issue tracker para agentes IA — tasks versionadas e rastreáveis | `setup.sh` ou `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
| **RTK** (`rtk`) | Proxy de tokens — 60-90% de economia em operações shell | `setup.sh` ou `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh \| sh && rtk init -g` |

Quando instalados, `setup.sh` detecta automaticamente e registra em `harness.yaml` → seção `integrations`.

### Comandos essenciais — Beads

```bash
bd ready          # Lista tasks prontas para trabalhar
bd create         # Cria uma nova issue/task
bd close <id>     # Fecha task concluída
bd dep add        # Adiciona dependência entre tasks
```

### RTK — como funciona

`rtk init -g` instala um hook global no Claude Code (`~/.claude/`) que intercepta comandos transparentemente.
Para verificar economia acumulada: `rtk gain`.

---

## Referências

- `AGENTS.md` — Constituição do swarm
- `~/.kanban-cortex-harness-agents/config/pipeline.yaml` — Configuração do pipeline
- `~/.kanban-cortex-harness-agents/templates/` — Templates de steering
