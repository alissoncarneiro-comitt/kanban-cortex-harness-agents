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
- Board: `python3 ~/.kanban-cortex-harness-agents/cockpit/server.py`

## Bootstrap

Execute `/a-bootstrap` uma vez por máquina/projeto para inicializar `.agents/`.
```

### 8. Criar .github/copilot-instructions.md (se ausente)

GitHub Copilot lê por projeto — não existe instalação global para Copilot.

```bash
mkdir -p .github
# copiar de ~/.kanban-cortex-harness-agents/templates/copilot-instructions.md
# apenas se .github/copilot-instructions.md não existir
```

### 9. Registrar projeto no hub de projetos

Registrar o projeto atual no registry global para o cockpit exibir o hub multi-projeto.
Executar o seguinte Python (idempotente — não sobrescreve entradas existentes do mesmo projeto):

```python
import sys, re
from pathlib import Path

_agent_home = Path.home() / ".kanban-cortex-harness-agents"
sys.path.insert(0, str(_agent_home))

from scripts.cockpit.project_registry import (
    load_project_registry, save_project_registry,
    add_or_update_project, ProjectEntry,
)

_registry_path = _agent_home / "config" / "project-registry.yaml"
_cwd = Path.cwd()
_project_id = re.sub(r"[^a-z0-9-]", "-", _cwd.name.lower()).strip("-") or "project"

_registry = load_project_registry(_registry_path)
_entry = ProjectEntry(project_id=_project_id, name=_cwd.name, root_path=_cwd)
_registry = add_or_update_project(_registry, _entry)
save_project_registry(_registry_path, _registry)
print(f"Hub: projeto '{_project_id}' registrado em {_registry_path}")
```

Falhas são silenciosas (não bloqueia o bootstrap).

### 10. Inicializar Beads (se habilitado)

Se `integrations.beads.enabled: true` em `~/.kanban-cortex-harness-agents/harness.yaml` e `bd` disponível, inicializar banco Beads na **raiz do repositório git** (não no subdiretório atual):

```bash
_HARNESS_YAML="$HOME/.kanban-cortex-harness-agents/harness.yaml"
_BEADS_ENABLED=$(python3 -c "
import sys, pathlib
try:
    import yaml
    d = yaml.safe_load(pathlib.Path('$_HARNESS_YAML').read_text()) or {}
    print('true' if d.get('integrations', {}).get('beads', {}).get('enabled') else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")

# Encontrar a raiz git mais externa (sobe até achar o .git mais alto)
_find_outermost_git_root() {
    local _dir="$PWD" _root=""
    while [ "$_dir" != "/" ]; do
        [ -d "$_dir/.git" ] && _root="$_dir"
        _dir=$(dirname "$_dir")
    done
    echo "${_root:-$PWD}"
}

if [ "$_BEADS_ENABLED" = "true" ] && command -v bd &>/dev/null; then
    _BEADS_ROOT=$(_find_outermost_git_root)
    if [ ! -d "$_BEADS_ROOT/.beads" ]; then
        (cd "$_BEADS_ROOT" && bd init --stealth 2>/dev/null) \
            && echo "   ✅ Beads inicializado em $_BEADS_ROOT/.beads/" \
            || echo "   ⚠️  Falha — rode 'cd $_BEADS_ROOT && bd init --stealth' manualmente"
    else
        echo "   ℹ️  Beads já inicializado em $_BEADS_ROOT/.beads/"
    fi
fi
```

`--stealth` exclui `.beads/` via `.git/info/exclude` (local, não commitado).
Falhas são silenciosas (não bloqueia o bootstrap).

### 11. Iniciar Cockpit (Kanban Board UI)

Iniciar o servidor Cockpit em background para visualização em tempo real:

```bash
python3 ~/.kanban-cortex-harness-agents/cockpit/check.py
```

O `check.py` é idempotente — se o servidor já estiver rodando, não faz nada.
Falhas são silenciosas (o board é opcional, não bloqueia o trabalho).

Confirmar ao usuário: "Cockpit disponível em http://127.0.0.1:8337"

### 10. Output final

```
✅ Projeto inicializado!

  .agents/kanban/    ← Quadro Kanban (local, não versionado)
  .agents/steering/  ← Memória do projeto (versionada)
  .agents/memory/    ← Memória dos agentes
  .agents/decisions/ ← Log de decisões arquitetural
  specs/             ← Specs aprovadas
  docs/              ← Documentação Diataxis

🔌 Integrações ativas: [listar se beads.enabled ou rtk.enabled]
   Beads: .beads/ pronto — use 'bd ready' para ver tasks
   RTK:   ativo — use 'rtk gain' para ver economia

🖥️  Cockpit (Kanban Board): http://127.0.0.1:8337

Próximos passos:
  /a-steering        → Configure produto, tech, convenções
  /a-discover "ideia"   ou   /a-po "prompt"
```
