---
name: a-bootstrap
aliases: ["/a-bootstrap", "/a-setup"]
description: >-
  Bootstrap de projeto: inicializa a estrutura .agents/ no projeto atual.
  Use uma vez por projeto, logo após clonar ou ao adicionar o harness.
  Nunca sobrescreve dados existentes. Requer ~/.kanban-cortex-harness-agents/ instalado (rode setup.sh primeiro).
---

# a-bootstrap — Bootstrap de Projeto

Inicializa a estrutura `.agents/` local no projeto atual a partir dos templates em `~/.kanban-cortex-harness-agents/`.

## Pré-condições

1. `~/.kanban-cortex-harness-agents/` deve existir — rode `setup.sh` do harness se ainda não fez
2. Execute da raiz do projeto (onde ficará `.agents/`)

## Workflow

### 1. Verificar pré-condições

```bash
[ -d "$HOME/.kanban-cortex-harness-agents" ] || { echo "❌ ~/.kanban-cortex-harness-agents/ não encontrado. Rode setup.sh primeiro."; exit 1; }
```

Se `.agents/swarm.yaml` já existir, perguntar ao usuário se quer reinicializar (nunca sobrescrever silenciosamente).

### 2. Criar estrutura de diretórios

Criar os diretórios abaixo apenas se não existirem (`mkdir -p`):

```
.agents/
  kanban/
    backlog/
    in-progress/
    done/
    reviews/
    audit/
    daily-logs/
  steering/
  memory/
  decisions/
specs/
  active/
  archive/
docs/
  tutorial/
  how-to/
  reference/
  explanation/
  examples/
tests/
  regression/
```

Criar symlink `kanban → .agents/kanban` na raiz do projeto (se não existir).

### 3. Copiar templates de steering

De `~/.kanban-cortex-harness-agents/templates/` para `.agents/steering/` (sem sobrescrever existentes):

| Template | Destino |
|---|---|
| `steering-product.md` | `.agents/steering/product.md` |
| `steering-tech.md` | `.agents/steering/tech.md` |
| `steering-conventions.md` | `.agents/steering/conventions.md` |
| `decision-log.md` | `.agents/steering/decision-log.md` |
| `roadmap.md` | `.agents/steering/roadmap.md` |

### 4. Copiar swarm.yaml

De `~/.kanban-cortex-harness-agents/config/` copiar `../` → criar `.agents/swarm.yaml` se não existir.
Alternativa: usar `~/.kanban-cortex-harness-agents/.agents/swarm.yaml` como template.

Substituir no arquivo:
- `name: "Agent Harness Engineering Kanban"` → `name: "<nome do diretório atual>"`

### 5. Inicializar board.yaml

Criar `.agents/kanban/board.yaml` mínimo se não existir:

```yaml
version: "1.0.0"
project: "<nome do diretório atual>"
created: "<data hoje YYYY-MM-DD>"
backlog: []
in_progress: []
done: []
```

### 6. Atualizar .gitignore

Verificar se `.gitignore` existe e adicionar entradas se ausentes:

```gitignore
# Kanban Cortex — runtime state (não commitar)
.agents/kanban/in-progress/
.agents/kanban/done/
.agents/kanban/reviews/
.agents/kanban/audit/
.agents/kanban/daily-logs/
```

Manter `.agents/steering/`, `.agents/swarm.yaml`, `.agents/decisions/` versionados.

### 7. Criar AGENTS.md se ausente

Se não existir `AGENTS.md` na raiz, criar um mínimo referenciando o harness:

```markdown
# AGENTS.md

Este projeto usa o **Kanban Cortex Harness**.

- Framework: `~/.kanban-cortex-harness-agents/`
- Comandos: `/a-discover`, `/a-po`, `/a-spec`, `/a-build`, `/a-review`, `/a-test`, `/a-ship`
- Board: `python3 ~/.kanban-cortex-harness-agents/cookip/server.py`

## Bootstrap

Execute `/a-bootstrap` uma vez por máquina/projeto para inicializar `.agents/`.
```

### 8. Output final

```
✅ Projeto inicializado!

  .agents/kanban/    ← Quadro Kanban (local, não versionado)
  .agents/steering/  ← Memória do projeto (versionada)
  .agents/memory/    ← Memória dos agentes
  .agents/decisions/ ← Log de decisões arquitetural
  specs/             ← Specs aprovadas
  docs/              ← Documentação Diataxis

Próximos passos:
  /a-steering   → Configure produto, tech, convenções
  /a-discover "ideia"   ou   /a-po "prompt"

Board Kanban:
  python3 ~/.kanban-cortex-harness-agents/cookip/server.py
```
