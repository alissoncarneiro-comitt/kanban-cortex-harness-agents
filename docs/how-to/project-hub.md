# How To: usar o Project Hub no cockpit

O cockpit pode operar em dois modos:

- `project`: o board e os artefatos são lidos a partir do projeto atual.
- `hub`: o cockpit navega por um registro global de projetos instalado em `~/.kanban-cortex-harness-agents/`.

## Quando usar

- Use `project` quando estiver trabalhando em um único repositório.
- Use `hub` quando o mesmo cockpit precisar alternar entre vários projetos.

## Como funciona

1. `setup.sh --all` instala o harness global e cria o diretório do hub.
2. `/a-bootstrap` registra o projeto atual no hub global.
3. O cockpit expõe `GET /api/projects` para listar os projetos conhecidos.
4. A UI mostra um seletor de projeto e origem no header.
5. A seleção ativa é persistida por `query param` e `localStorage`.

## Arquivos importantes

- Registro global: `~/.kanban-cortex-harness-agents/config/project-registry.yaml`
- Board local do projeto: `.agents/kanban/board.yaml`
- Cockpit UI: `src/cockpit/board.html`

## Exemplos de navegação

Abrir um projeto específico:

```text
http://127.0.0.1:8337/?project_id=alpha&source=project
```

Listar os projetos registrados via API:

```text
GET /api/projects
```

## Boas práticas

- Mantenha `project_id` estável e legível.
- Registre cada projeto uma única vez no hub.
- Use `source=project` como padrão quando o board estiver no próprio repositório.
- Use `source=hub` quando a origem operacional estiver centralizada no ambiente global.
