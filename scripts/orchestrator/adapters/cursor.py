"""Cursor / agent CLI adapter (FEAT-011 TASK-001)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .claude import strip_skill_frontmatter


class CursorAdapter:
    name = "cursor"

    def invoke(
        self,
        skill_path: Path,
        item_id: str,
        *,
        base_dir: Path,
        task_id: str | None = None,
        cwd: Path | None = None,
    ) -> int:
        agent_bin = shutil.which("agent")
        if agent_bin is None:
            print(
                "Cursor agent CLI ausente no PATH. Instale o Cursor CLI (`agent`) "
                "ou use pipeline.invoker: claude.",
                file=sys.stderr,
            )
            return 1
        resolved = skill_path
        if not resolved.is_file():
            candidate = base_dir / skill_path
            if candidate.is_file():
                resolved = candidate
            else:
                print(f"skill file não encontrado: {skill_path}", file=sys.stderr)
                return 1
        body = strip_skill_frontmatter(resolved.read_text(encoding="utf-8"))
        prompt = f"{body}\n\nITEM={item_id}\n"
        if task_id:
            prompt += f"TASK={task_id}\n"
        env = os.environ.copy()
        env.setdefault("CURSOR_AGENT", "1")
        completed = subprocess.run(
            [agent_bin, "-p", prompt],
            cwd=str(cwd or base_dir),
            env=env,
            check=False,
        )
        return int(completed.returncode)
