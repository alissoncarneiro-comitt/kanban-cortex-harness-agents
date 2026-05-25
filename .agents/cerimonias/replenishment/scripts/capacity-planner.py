#!/usr/bin/env python3
"""
Calcula capacidade atual do swarm e slots disponíveis para replenishment.

Paths resolvidos em ordem:
  1. KANBAN_ROOT env var
  2. Auto-detecção: sobe a árvore procurando .agents/kanban/board.yaml
  3. Fallback: .agents/kanban/ relativo ao Cwd
"""

import os
import yaml
from pathlib import Path


def _resolve_kanban_root() -> Path:
    env = os.environ.get("KANBAN_ROOT")
    if env:
        return Path(env)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".agents" / "kanban"
        if (candidate / "board.yaml").exists():
            return candidate
    return Path(".agents/kanban")


_KANBAN_ROOT = _resolve_kanban_root()
BOARD = _KANBAN_ROOT / "board.yaml"
SWARM = _KANBAN_ROOT.parent.parent / ".agents" / "swarm.yaml"

def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

def capacity_check():
    board = load_yaml(BOARD)
    swarm = load_yaml(SWARM)

    wip_total = swarm.get("kanban", {}).get("wip_limit_total", 10)
    wip_per_agent = swarm.get("kanban", {}).get("wip_limit_per_agent", 3)

    columns = board.get("board", {}).get("columns", [])
    in_progress_count = sum(c.get("count", 0) for c in columns if c["name"] not in ["Backlog", "Done"])

    slots_free = wip_total - in_progress_count

    print(f"=== CAPACITY CHECK ===")
    print(f"WIP Total Limit: {wip_total}")
    print(f"WIP Per Agent:   {wip_per_agent}")
    print(f"In Progress:     {in_progress_count}")
    print(f"Slots Free:      {slots_free}")
    print(f"Can Replenish:   {'YES' if slots_free > 0 else 'NO'}")

    return slots_free

if __name__ == "__main__":
    capacity_check()
