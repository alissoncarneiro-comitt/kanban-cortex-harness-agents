# Recuperar estado do board Kanban

Playbook para corrigir inconsistências em `.agents/kanban/board.yaml` e alinhar o Cockpit com o pipeline.

## phase-column-drift

**Sintoma:** `board-validate.py` emite `PHASE COLUMN DRIFT` — o item está numa coluna anterior à indicada por `phase_status` em `task.yaml`.

**Exemplo:** `phase_status.build: done` mas o card ainda está em `build` (deveria estar pelo menos em `review`).

**Causa comum:** handoff ou gate de steering concluído sem promoção automática (`BOARD_AUTO_PROMOTE=false`, falha best-effort de `board_promote`, ou edição manual).

**Correção:**

```bash
# Derivar trigger do último handoff conhecido, por exemplo:
python scripts/orchestrator/board_promote.py --item FEAT-XXX --trigger handoff.build.done

# Ou via gate de steering:
python scripts/steering-gate.py --item FEAT-XXX --gate approve-tasks
```

Ver também [board-phase-promotion.md](./board-phase-promotion.md) (FEAT-013) para a matriz completa de transições.

## yaml-invalido

**Sintoma:** `board-validate.py` falha ao parsear YAML.

**Correção:** Restaure `board.yaml` a partir do git (`git checkout -- .agents/kanban/board.yaml`) ou corrija indentação/chaves duplicadas manualmente.

## wip-overflow

**Sintoma:** WIP total ou por coluna excedido.

**Correção:** Mova cards para `done` ou `backlog`, ou aumente temporariamente o limite no YAML (policy expedite).

## lock-violation

**Sintoma:** `design.md` modificado após tag `[LOCKED — approved YYYY-MM-DD]`.

**Correção:** Reverta alterações não autorizadas ou inicie novo ciclo de spec com human gate.

## orphan-branch

**Sintoma:** branch `feature/FEAT-XXX-*` sem item correspondente no board.

**Correção:** Merge/delete a branch ou adicione o item ao board.

## orphan-item

**Sintoma:** diretório em `.agents/kanban/in-progress/FEAT-XXX` sem card no board.

**Correção:** Adicione o card à coluna correta ou arquive o item.
