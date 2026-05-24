"""WIP Reporter por Squad — FEAT-006 TASK-002.

Feature flag: HARNESS_FEATURE_SQUAD_NAMESPACE_V1 (default OFF until /a-ship).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import yaml

from scripts.squad.manager import SquadConfig, resolve_squad

_EXCLUDED_COLUMNS = {"backlog", "done"}


def report(board_yaml_path: Path, squad_config: list[SquadConfig]) -> dict[str, int]:
    """Conta itens WIP por squad, excluindo backlog e done.

    Retorna dict com squad_id → count e chave 'total'.
    Modo solo (squad_config=[]) retorna apenas {'default': N, 'total': N}.
    """
    if not board_yaml_path.exists():
        raise FileNotFoundError(f"HARNESS ERROR: board.yaml not found: {board_yaml_path}")

    raw = board_yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    items_by_col: dict[str, list] = data.get("board", {}).get("items", {})

    counts: dict[str, int] = {}
    if squad_config:
        for squad in squad_config:
            counts[squad.id] = 0
    counts["default"] = 0

    for col_name, col_items in items_by_col.items():
        if col_name in _EXCLUDED_COLUMNS:
            continue
        if not col_items:
            continue
        for item in col_items:
            item_id = str(item.get("id", ""))
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                squad_id = resolve_squad(item_id, squad_config)
            if squad_id not in counts:
                counts[squad_id] = 0
            counts[squad_id] += 1

    total = sum(v for k, v in counts.items() if k != "total")
    counts["total"] = total
    return counts


def format_report(data: dict[str, int]) -> str:
    """Formata dict de WIP como string 'squad1: N | squad2: N | total: N'."""
    parts = []
    for key, val in data.items():
        if key == "total":
            continue
        parts.append(f"{key}: {val}")
    total = data.get("total", 0)
    parts.append(f"total: {total}")
    return " | ".join(parts)


def filter_report(data: dict[str, int], squad: str) -> dict[str, int]:
    """Filtra relatório para apenas o squad especificado + total."""
    return {k: v for k, v in data.items() if k in (squad, "total")}


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    from scripts.squad.manager import load_squad_config

    parser = argparse.ArgumentParser(description="Reporta WIP por squad.")
    parser.add_argument("--board", default=".agents/kanban/board.yaml", help="Caminho para board.yaml")
    parser.add_argument("--swarm", default=".agents/swarm.yaml", help="Caminho para swarm.yaml")
    parser.add_argument("--squad", default=None, help="Filtrar saída por squad específico")
    args = parser.parse_args()

    board_path = Path(args.board)
    swarm_path = Path(args.swarm)

    try:
        config = load_squad_config(swarm_path)
        data = report(board_path, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    result = filter_report(data, args.squad) if args.squad else data
    print(format_report(result))
