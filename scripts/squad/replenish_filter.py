"""Replenishment Filter por Squad — FEAT-006 TASK-003.

Feature flag: HARNESS_FEATURE_SQUAD_NAMESPACE_V1 (default OFF until /a-ship).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import yaml

from scripts.squad.manager import SquadConfig, resolve_squad


def filter_backlog(
    board_yaml_path: Path,
    squad: Optional[str],
    config: list[SquadConfig],
) -> list[dict]:
    """Retorna itens do backlog filtrados por squad, ordenados por wsjf_score DESC.

    squad=None → comportamento legado (todos os itens).
    squad="default" → apenas itens sem prefixo de squad conhecido.
    squad="alpha" → apenas itens do squad alpha.

    Cada item retornado recebe campo 'squad' com o squad resolvido.
    """
    if not board_yaml_path.exists():
        raise FileNotFoundError(f"HARNESS ERROR: board.yaml not found: {board_yaml_path}")

    raw = board_yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    backlog: list = data.get("board", {}).get("items", {}).get("backlog", []) or []

    enriched: list[dict] = []
    for item in backlog:
        item_id = str(item.get("id", ""))
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            squad_id = resolve_squad(item_id, config)

        enriched_item = dict(item)
        enriched_item["squad"] = squad_id
        enriched.append(enriched_item)

    if squad is not None:
        enriched = [i for i in enriched if i["squad"] == squad]

    enriched.sort(key=lambda i: float(i.get("wsjf_score", 0)), reverse=True)
    return enriched


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json
    import sys

    from scripts.squad.manager import load_squad_config

    parser = argparse.ArgumentParser(description="Filtra backlog por squad.")
    parser.add_argument("--board", default=".agents/kanban/board.yaml", help="Caminho para board.yaml")
    parser.add_argument("--swarm", default=".agents/swarm.yaml", help="Caminho para swarm.yaml")
    parser.add_argument("--squad", default=None, help="Filtrar por squad (ou 'default' para legados)")
    args = parser.parse_args()

    board_path = Path(args.board)
    swarm_path = Path(args.swarm)

    try:
        config = load_squad_config(swarm_path)
        items = filter_backlog(board_path, squad=args.squad, config=config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(items, ensure_ascii=False, indent=2))
