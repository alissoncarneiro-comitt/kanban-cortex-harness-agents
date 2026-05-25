# Kanban Cortex Harness Agents

> **Spec-Driven + Role-Based + Kanban-Flow** para Agent Swarms de Engenharia.
> Suporte: Claude Code · Codex CLI · Cursor · Windsurf · Devin CLI · Antigravity

## Filosofia

**Menos é mais.** 7 papéis, 3 cerimônias, 6 artefatos. Cada papel é um skill independente.
O harness é instalado **globalmente** na máquina — os projetos ficam limpos.

---

## Instalação Rápida

```bash
git clone https://github.com/alissoncarneiro-comitt/kanban-cortex-harness-agents
cd kanban-cortex-harness-agents
./setup.sh          # auto-detecta os agents instalados na máquina
```

Instala o framework em `~/.kanban-cortex-harness-agents/` e cria symlinks nos agents detectados.

### Instalar agent específico

```bash
./setup.sh --claude       # Claude Code   → ~/.claude/skills/ + ~/.claude/commands/
./setup.sh --codex        # Codex CLI     → ~/.codex/skills/
./setup.sh --cursor       # Cursor        → ~/.cursor/skills/
./setup.sh --windsurf     # Windsurf      ��� ~/.codeium/windsurf/skills/
./setup.sh --devin        # Devin CLI     → ~/.config/devin/skills/
./setup.sh --antigravity  # Antigravity   → ~/.gemini/antigravity/skills/
./setup.sh --all          # Todos
```

### Atualizar

```bash
cd kanban-cortex-harness-agents
git pull origin main && ./setup.sh --update   # re-sync ~/.kanban-cortex-harness-agents/
```

Regra prática: sempre faça `git pull` de dentro de `kanban-cortex-harness-agents/`, nunca da raiz do workspace.

---

## Inicializar um Projeto

Após instalar o harness, rode em qualquer projeto:

```bash
cd meu-projeto

# Claude Code
/a-bootstrap

# Codex CLI
$a-bootstrap
```

Cria `.agents/kanban/`, `.agents/steering/`, `.agents/memory/` — o projeto fica com apenas dados locais.

---

## Compatibilidade por OS

| OS | Funciona? |
|---|---|
| Linux | ✅ |
| macOS | ✅ |
| WSL | ✅ (usa `~` do Linux) |
| Windows (Git Bash / MSYS) | ✅ |

---

## Estrutura do Harness Global

```
~/.kanban-cortex-harness-agents/
├── skills/
│   ├── 05-bootstrap/   ← /a-bootstrap  (inicializa projetos)
│   ├── 00-steering/    ← /a-steering
│   ├─�� 10-discovery/   ← /a-discover
│   ├── 15-po/          ← /a-po
│   ├── 20-spec/        ← /a-spec
│   ├── 30-design/      ← /a-design
│   ├── 40-build/       ← /a-build
│   ├── 50-review/      ← /a-review
│   ├── 60-test/        ← /a-test
│   ├── 70-ship/        ← /a-ship
│   └── 80-governance/  ← /a-governance
├── commands/           ← /a-flow, /a-plan, /a-reflect, /a-replenish
├── cerimonias/         ← daily-flow, replenishment, service-delivery-review
├── cockpit/             ← Kanban Board UI (server.py + board.html)
├── config/             ��� pipeline.yaml
├─�� templates/          ← steering templates
└── scripts/            ← orchestrator, board-validate, metrics, etc.
```

Symlinks criados pelo `setup.sh`:

```
~/.claude/skills/a-bootstrap   →  ~/.kanban-cortex-harness-agents/skills/05-bootstrap
~/.claude/skills/a-steering    →  ~/.kanban-cortex-harness-agents/skills/00-steering
~/.claude/skills/a-build       →  ~/.kanban-cortex-harness-agents/skills/40-build
... (todos os /a-* apontam para ~/.kanban-cortex-harness-agents/skills/)

~/.codex/skills/a-bootstrap    ���  ~/.kanban-cortex-harness-agents/skills/05-bootstrap
~/.cursor/skills/a-bootstrap   →  ~/.kanban-cortex-harness-agents/skills/05-bootstrap
~/.codeium/windsurf/skills/... →  ~/.kanban-cortex-harness-agents/skills/...
```

---

## Estrutura do Projeto (após /a-bootstrap)

```
meu-projeto/
├── .agents/
│   ├── kanban/         ← Board local (não commitado)
│   ├── steering/       ← product.md, tech.md, conventions.md (commitado)
│   ├── memory/
│   ├── decisions/
│   └── swarm.yaml
├── specs/              ← Specs aprovadas
├── docs/               ← Documentação Diataxis
├── kanban → .agents/kanban
└── AGENTS.md
```

---

## Pipeline Spec-Driven

```
/a-bootstrap  →  /a-steering  →  /a-discover ou /a-po
                                          ↓
              /a-spec  →  /a-design  →  /a-build  →  /a-review  →  /a-test  →  /a-ship
```

---

## Board Kanban (Cockpit)

```bash
cd meu-projeto
python3 ~/.kanban-cortex-harness-agents/cockpit/server.py
# → http://127.0.0.1:8337
```

---

## Constituição

Ver [`AGENTS.md`](AGENTS.md) para a constituição completa do swarm.
