#!/usr/bin/env python3
"""
board_promote.py — Promove itens entre colunas do board.yaml (FEAT-013 TASK-001).

Sincroniza colunas do Kanban com gatilhos de handoff e gates de steering.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_BOARD_PATH = Path(".agents/kanban/board.yaml")

# trigger → coluna destino (design.md matriz de transição)
TRIGGER_TO_COLUMN: dict[str, str] = {
    "handoff.build.done": "review",
    "handoff.build.failed": "build",
    "handoff.review.approved": "test",
    "handoff.review.changes_requested": "build",
    "handoff.review.rejected": "build",
    "handoff.test.passed": "ship",
    "handoff.test.failed": "build",
    "handoff.ship.done": "done",
    "handoff.ship.failed": "ship",
    "steering.approve.brief": "spec",
    "steering.approve.tasks": "build",
    "discover.phase_start": "discover",
    "steering.approve.requirements": "spec",
}


@dataclass
class PromoteResult:
    ok: bool
    from_column: Optional[str] = None
    to_column: Optional[str] = None
    skipped: bool = False
    reason: Optional[str] = None
    message: Optional[str] = None


def trigger_from_handoff(phase: str, status: str) -> str:
    """Monta trigger canônico a partir de fase e status do handoff."""
    return f"handoff.{phase}.{status}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_board(board_path: Path) -> dict:
    if not board_path.is_file():
        raise FileNotFoundError(f"board.yaml not found: {board_path}")
    raw = board_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError("YAML_CORRUPT") from exc
    if not isinstance(data, dict) or "board" not in data:
        raise ValueError("invalid board structure")
    return data


def find_item_columns(board: dict, item_id: str) -> list[tuple[str, int]]:
    """Retorna lista de (coluna, índice) onde o item aparece."""
    items = board.get("board", {}).get("items", {}) or {}
    matches: list[tuple[str, int]] = []
    for column, entries in items.items():
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and str(entry.get("id")) == item_id:
                matches.append((column, index))
    return matches


def _resolve_target_column(trigger: str) -> Optional[str]:
    return TRIGGER_TO_COLUMN.get(trigger)


def _write_board_atomic(board_path: Path, data: dict) -> None:
    board_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = board_path.with_suffix(board_path.suffix + ".tmp")
    payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(board_path)


def _check_wip_warn(board: dict, target_column: str) -> Optional[str]:
    columns = board.get("board", {}).get("columns", []) or []
    counts: dict[str, int] = {}
    items = board.get("board", {}).get("items", {}) or {}
    for key, entries in items.items():
        counts[key] = len(entries) if isinstance(entries, list) else 0

    limit: Optional[int] = None
    for col in columns:
        if not isinstance(col, dict):
            continue
        name = str(col.get("name", "")).strip().lower().replace(" ", "_")
        if name == target_column:
            raw_limit = col.get("wip_limit")
            limit = int(raw_limit) if raw_limit is not None else None
            break

    if limit is None:
        return None
    if counts.get(target_column, 0) >= limit:
        return f"WIP_EXCEEDED: column {target_column} at limit {limit}"
    return None


def promote(
    item_id: str,
    trigger: str,
    *,
    board_path: Path | str | None = None,
) -> PromoteResult:
    """
    Move item_id para a coluna mapeada por trigger.

    Idempotente se já estiver na coluna destino.
    ITEM_NOT_ON_BOARD → ok=False, não lança.
    DUPLICATE_ITEM_ID → ValueError.
    """
    path = Path(board_path) if board_path is not None else DEFAULT_BOARD_PATH
    target = _resolve_target_column(trigger)
    if target is None:
        return PromoteResult(ok=True, skipped=True, reason="UNKNOWN_TRIGGER")

    board = load_board(path)
    matches = find_item_columns(board, item_id)

    if not matches:
        print(f"WARN: ITEM_NOT_ON_BOARD item={item_id} trigger={trigger}", file=sys.stderr)
        return PromoteResult(ok=False, reason="ITEM_NOT_ON_BOARD")

    if len(matches) > 1:
        cols = ", ".join(col for col, _ in matches)
        raise ValueError(f"DUPLICATE_ITEM_ID: {item_id} found in {cols}")

    from_column, from_index = matches[0]
    if from_column == target:
        return PromoteResult(
            ok=True,
            from_column=from_column,
            to_column=target,
            skipped=True,
            reason="ALREADY_IN_TARGET",
        )

    wip_msg = _check_wip_warn(board, target)
    if wip_msg:
        print(f"WARN: {wip_msg}", file=sys.stderr)

    items = board["board"]["items"]
    source_list = items.setdefault(from_column, [])
    if not isinstance(source_list, list):
        raise ValueError(f"invalid items list for column {from_column}")

    card = source_list.pop(from_index)
    dest_list = items.setdefault(target, [])
    if not isinstance(dest_list, list):
        dest_list = []
        items[target] = dest_list
    dest_list.append(card)

    board["board"]["last_updated"] = _now_iso()
    _write_board_atomic(path, board)

    return PromoteResult(ok=True, from_column=from_column, to_column=target)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Promote Kanban item column")
    parser.add_argument("--item", required=True, help="Item id e.g. FEAT-013")
    parser.add_argument("--trigger", required=True, help="Trigger key e.g. handoff.build.done")
    parser.add_argument("--board", default=str(DEFAULT_BOARD_PATH), help="Path to board.yaml")
    args = parser.parse_args()

    try:
        result = promote(args.item, args.trigger, board_path=Path(args.board))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if result.skipped and result.reason == "UNKNOWN_TRIGGER":
        print(f"noop: unknown trigger {args.trigger}")
        return 0
    if not result.ok:
        print(f"skipped: {result.reason}")
        return 0
    if result.skipped:
        print(f"idempotent: {args.item} already in {result.to_column}")
        return 0

    print(f"promoted: {args.item} {result.from_column} -> {result.to_column}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
