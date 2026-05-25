# Reference: project-registry.yaml

O `project-registry.yaml` é o catálogo canônico de projetos do cockpit em modo hub.

## Localização

- Instalação global: `~/.kanban-cortex-harness-agents/config/project-registry.yaml`
- Arquivo canônico no repositório: `config/project-registry.yaml`

## Estrutura

```yaml
version: "1.0"
projects:
  - project_id: alpha
    name: Alpha
    root_path: /home/alisson/workspace/alpha
    source_mode: project
    board_path: .agents/kanban/board.yaml
    active: true
```

## Campos

- `version`: versão do esquema do registry.
- `projects`: lista de projetos conhecidos.
- `project_id`: identificador estável usado na UI e na API.
- `name`: nome amigável exibido no cockpit.
- `root_path`: raiz do projeto no filesystem.
- `source_mode`: origem preferida do contexto.
- `board_path`: caminho do board relativo ao `root_path`, salvo se for absoluto.
- `active`: marca o projeto como preferido no seletor.

## Regras de leitura

- Se o arquivo não existir, o cockpit usa um registry vazio.
- `source_mode` desconhecido cai para `project`.
- `board_path` vazio volta para `.agents/kanban/board.yaml`.
- `root_path` vazio ou inválido deve falhar ao carregar.

## Fluxo esperado

1. O bootstrap registra ou atualiza o projeto no registry.
2. O cockpit lê o registry para montar a lista de projetos.
3. O usuário escolhe `project_id` e `source`.
4. O servidor resolve board, item e artefatos a partir desse contexto.
