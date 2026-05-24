"""Claude Code CLI adapter (FEAT-011 TASK-001)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .base import PhaseAdapter


def strip_skill_frontmatter(content: str) -> str:
    """Remove YAML frontmatter so `claude -p` does not parse `---` as CLI flags."""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2].lstrip("\n")
    return content


class ClaudeAdapter:
    name = "claude"

    def invoke(
        self,
        skill_path: Path,
        item_id: str,
        *,
        base_dir: Path,
        task_id: str | None = None,
        cwd: Path | None = None,
    ) -> int:
        if shutil.which("claude") is None:
            print(
                "claude CLI ausente no PATH. Instale Claude Code ou use pipeline.invoker: cursor.",
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
        completed = subprocess.run(
            ["claude", "-p", prompt],
            cwd=str(cwd or base_dir),
            check=False,
        )
        return int(completed.returncode)
