# Steering — Structure

> Gerado por `/a-steering init`. Layout do repositório e ownership.

## Diretórios Principais

```
.agents/           # Cérebro do swarm (skills, kanban, steering, memória)
├── skills/        # Agent Skills canônicos
├── steering/      # Memória persistente (este diretório)
├── kanban/        # Estado do quadro
└── memory/        # Learnings e identity souls

specs/             # Specs aprovadas (active/ + archive/)
src/               # Código-fonte
tests/             # Testes (unit/integration/e2e)
docs/              # Documentação Diataxis
templates/         # Artefatos-contrato
decisions/         # ADRs
```

## Módulos e Ownership

| Módulo | Path | Owner | Boundaries |
|--------|------|-------|------------|
| [Nome] | `src/...` | [Agente/Pessoa] | [Arquivos permitidos] |

## Kanban Paths

- Backlog: `.agents/kanban/backlog/{ITEM}/`
- Em progresso: `.agents/kanban/in-progress/{ITEM}/`
- Concluído: `.agents/kanban/done/{ITEM}/`

## Referências

- cc-sdd: specs como contratos entre partes do sistema
- Kanban: WIP limits em `.agents/kanban/board.yaml`
