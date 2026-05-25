#!/usr/bin/env python3
"""
steering-gate.py — Promove coluna do board após gates humanos (FEAT-013 TASK-003).

Uso:
    python scripts/steering-gate.py --item FEAT-013 --gate approve-brief
    python scripts/steering-gate.py --item FEAT-013 --gate approve-tasks
    python scripts/steering-gate.py --item FEAT-013 --gate discover-start
    python scripts/steering-gate.py --item FEAT-013 --trigger steering.approve.brief
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Permite execução com PYTHONPATH=scripts
try:
    from orchestrator.board_promote import DEFAULT_BOARD_PATH, promote
except ImportError:  # pragma: no cover
    from board_promote import DEFAULT_BOARD_PATH, promote  # type: ignore

GATE_TRIGGERS: dict[str, str] = {
    "approve-brief": "steering.approve.brief",
    "approve-tasks": "steering.approve.tasks",
    "approve-requirements": "steering.approve.requirements",
    "discover-start": "discover.phase_start",
}


def _auto_promote_enabled() -> bool:
    value = os.environ.get("BOARD_AUTO_PROMOTE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def run_gate(
    item_id: str,
    *,
    gate: str | None = None,
    trigger: str | None = None,
    board_path: Path | str | None = None,
) -> int:
    if not _auto_promote_enabled():
        print(f"skip: BOARD_AUTO_PROMOTE disabled for {item_id}")
        return 0

    resolved_trigger = trigger
    if gate is not None:
        if gate not in GATE_TRIGGERS:
            print(
                f"ERROR: gate inválido '{gate}'. Opções: {', '.join(sorted(GATE_TRIGGERS))}",
                file=sys.stderr,
            )
            return 1
        resolved_trigger = GATE_TRIGGERS[gate]

    if not resolved_trigger:
        print("ERROR: informe --gate ou --trigger", file=sys.stderr)
        return 1

    path = Path(board_path) if board_path is not None else DEFAULT_BOARD_PATH
    try:
        result = promote(item_id, resolved_trigger, board_path=path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(f"WARN: board promote falhou: {exc}", file=sys.stderr)
        return 0

    if not result.ok:
        print(f"WARN: {item_id} trigger={resolved_trigger} reason={result.reason}", file=sys.stderr)
        return 0
    if result.skipped:
        print(f"noop: {item_id} already in {result.to_column or 'target'}")
        return 0

    print(f"promoted: {item_id} {result.from_column} -> {result.to_column}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promove item no board.yaml após gate humano ou início de discover.",
    )
    parser.add_argument("--item", required=True, help="ID do item (ex: FEAT-013)")
    parser.add_argument(
        "--gate",
        choices=sorted(GATE_TRIGGERS),
        help="Gate canônico (mapeia para trigger interno)",
    )
    parser.add_argument(
        "--trigger",
        help="Trigger explícito (ex: steering.approve.brief)",
    )
    parser.add_argument(
        "--board",
        default=str(DEFAULT_BOARD_PATH),
        help="Caminho para board.yaml",
    )
    args = parser.parse_args(argv)

    if args.gate and args.trigger:
        print("ERROR: use apenas --gate ou --trigger", file=sys.stderr)
        return 1

    return run_gate(
        args.item,
        gate=args.gate,
        trigger=args.trigger,
        board_path=Path(args.board),
    )


if __name__ == "__main__":
    raise SystemExit(main())
