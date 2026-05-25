# Promoção automática de fases no board

Como sincronizar a coluna do Kanban (`board.yaml`) com handoffs do pipeline e gates de steering — sem editar o board manualmente.

## Quando usar

- Após `/a-steering approve brief` ou `approve tasks`
- Quando `handoff.py` registra conclusão de fase (`build`, `review`, `test`, `ship`)
- Ao iniciar `/a-discover` (item sai de `backlog` → `discover`)

A promoção é **best-effort**: falhas no board não revertem o handoff em `task.yaml`.

## Matriz de transição

| Gatilho | Coluna destino |
|---------|----------------|
| `handoff build done` | review |
| `handoff build failed` | build |
| `handoff review approved` | test |
| `handoff review changes_requested` | build |
| `handoff review rejected` | build |
| `handoff test passed` | ship |
| `handoff test failed` | build |
| `handoff ship done` | done |
| `handoff ship failed` | ship |
| `steering approve brief` | spec |
| `steering approve tasks` | build |
| `steering approve requirements` | spec |
| `discover phase_start` | discover |

Origem: o módulo localiza o item por `id` em **qualquer** coluna e move atomicamente (write temp + rename).

## Comandos

### Handoff (automático)

Todo handoff bem-sucedido chama `board_promote` internamente:

```bash
python scripts/orchestrator/handoff.py --item FEAT-013 --phase build --status done
```

Handoffs por task (`--task TASK-NNN` em build) **não** promovem coluna até o handoff de fase completa.

### Gates de steering (manual pelo agente)

```bash
python scripts/steering-gate.py --item FEAT-013 --gate approve-brief
python scripts/steering-gate.py --item FEAT-013 --gate approve-tasks
python scripts/steering-gate.py --item FEAT-013 --gate discover-start
```

### Promoção direta (debug)

```bash
python scripts/orchestrator/board_promote.py --item FEAT-013 --trigger handoff.build.done
```

## `/a-po` vs `/a-discover` e o board

| Entrada | Primeira promoção típica | Gate humano → coluna |
|---------|------------------------|----------------------|
| **`/a-discover`** (escopo vago) | `discover-start`: backlog → discover | `approve brief` → spec |
| **`/a-po "prompt"`** (escopo claro) | item pode ir direto a spec após requirements | `approve tasks` → build |

Ambos os caminhos convergem em **spec → build** após `approve tasks`, depois o pipeline (`handoff`) leva review → test → ship → done.

## Variáveis de ambiente

| Variável | Default | Efeito |
|----------|---------|--------|
| `BOARD_AUTO_PROMOTE` | `true` | `false` desliga promoção em `handoff.py` e `steering-gate.py` |

## Troubleshooting

### Item na coluna errada

1. Verifique drift:

```bash
python scripts/board-validate.py --item FEAT-013
# ou
python scripts/board-validate.py --full
```

2. Corrija com o trigger adequado (ver matriz acima) ou consulte [recover-board-state.md](./recover-board-state.md#phase-column-drift).

### Promoção não ocorreu após handoff

- Confirme `BOARD_AUTO_PROMOTE` não está `false`
- Handoff com `--task` em build não promove (esperado)
- Item ausente do board → WARN `ITEM_NOT_ON_BOARD`; handoff ainda persiste

### WIP excedido

Promoção **continua** com WARN (policy expedite). Reduza WIP ou mova cards manualmente se necessário.

## Referências

- [recover-board-state.md](./recover-board-state.md) — playbook de correção
- `scripts/orchestrator/board_promote.py` — implementação
- FEAT-013 `design.md` — contrato locked
