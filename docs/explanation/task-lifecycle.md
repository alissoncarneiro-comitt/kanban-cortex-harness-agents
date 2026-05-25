# Ciclo de Vida das Tasks

Este documento explica a taxonomia canônica de estados de task utilizada no Agent Harness para garantir visibilidade e consistência operacional.

## Estados Canônicos

Para simplificar o rastreamento do progresso, todas as tasks em Build, Review e QA seguem os mesmos estados:

| Estado | Descrição | Cor no Board |
|--------|-----------|--------------|
| `pending` | Task criada mas ainda não iniciada. | Cinza |
| `in_progress` | Agente assumiu a execução e o trabalho está em curso. | Azul (com timer) |
| `complete` | Trabalho concluído com sucesso e verificado. | Verde |
| `failed` | Erro na execução ou timeout. | Vermelho |

## Fluxo de Transição Automática

O framework gerencia as transições de estado automaticamente através do pipeline e dos scripts de handoff:

1. **Inicialização (`pending`)**: Quando o pipeline lê o `tasks.md`, ele inicializa todas as tasks no `task.yaml` como `pending`.
2. **Execução (`in_progress`)**: Ao disparar o skill de uma task, o pipeline atualiza seu estado para `in_progress`.
3. **Conclusão (`complete`)**: Quando o agente invoca o `handoff.py` com um status de sucesso (`done`, `passed` ou `approved`), o estado da task é movido para `complete`.

## Guia para Agentes

Ao desenvolver ou atuar em uma task, você não precisa se preocupar em atualizar manualmente o estado no `task.yaml`. O uso correto das ferramentas do harness garante a consistência:

- **Build**: Ao terminar uma task, execute `python scripts/orchestrator/handoff.py --item ITEM --phase build --task TASK-NNN --status done`.
- **Review**: O reviewer usa `--status approved` para marcar a task como concluída.
- **QA**: O tester usa `--status passed` para marcar a task como concluída.

Todos esses comandos agora convergem para o estado `complete` no campo `task_progress` do `task.yaml`.
