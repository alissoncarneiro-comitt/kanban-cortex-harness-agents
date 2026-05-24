"""Phase invocation adapters for the Agent Harness pipeline (FEAT-011)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PhaseAdapter(Protocol):
    """Invokes a skill file for an item (optional task scope for DAG builds)."""

    name: str

    def invoke(
        self,
        skill_path: Path,
        item_id: str,
        *,
        base_dir: Path,
        task_id: str | None = None,
        cwd: Path | None = None,
    ) -> int:
        """Run the skill; return process exit code (0 = subprocess ok, not phase done)."""
