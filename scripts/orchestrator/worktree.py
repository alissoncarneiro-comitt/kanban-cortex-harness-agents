#!/usr/bin/env python3
"""
worktree.py — Git worktrees para build paralelo por TASK-NNN (FEAT-011 TASK-008).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class WorktreeError(RuntimeError):
    """Falha ao criar ou fundir worktree."""


def _dry_run_enabled() -> bool:
    return os.environ.get("HARNESS_WORKTREE_DRY_RUN", "").lower() in (
        "1",
        "true",
        "yes",
    )


class WorktreeManager:
    """Cria worktrees por task e funde num branch de integração."""

    def __init__(self, repo_root: Path, item_id: str, *, dry_run: bool | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.item_id = item_id
        self.dry_run = _dry_run_enabled() if dry_run is None else dry_run
        self.worktrees_root = self.repo_root / ".agents" / "worktrees" / item_id

    def integration_branch(self) -> str:
        return f"integration/{self.item_id}"

    def branch_for_task(self, task_id: str) -> str:
        return f"feat/{self.item_id}-{task_id}"

    def worktree_path(self, task_id: str) -> Path:
        return self.worktrees_root / task_id

    def create(self, task_id: str) -> Path:
        """Cria worktree (ou diretório dry-run) para a task."""
        path = self.worktree_path(task_id)
        branch = self.branch_for_task(task_id)
        if self.dry_run:
            path.mkdir(parents=True, exist_ok=True)
            marker = path / ".harness-worktree"
            marker.write_text(f"{self.item_id}:{task_id}:{branch}\n", encoding="utf-8")
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        try:
            subprocess.run(
                ["git", "worktree", "add", "-B", branch, str(path), "HEAD"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise WorktreeError(
                f"git worktree add falhou para {task_id} em {path}: {exc}"
            ) from exc
        return path

    def merge_to_integration(self, task_ids: list[str]) -> str:
        """Funde branches das tasks no branch de integração. Devolve nome do branch."""
        branch = self.integration_branch()
        if self.dry_run:
            merged = self.worktrees_root / ".merged-tasks"
            merged.parent.mkdir(parents=True, exist_ok=True)
            merged.write_text("\n".join(sorted(task_ids)) + "\n", encoding="utf-8")
            return branch
        try:
            subprocess.run(
                ["git", "branch", "-f", branch, "HEAD"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
            for task_id in task_ids:
                task_branch = self.branch_for_task(task_id)
                subprocess.run(
                    [
                        "git",
                        "merge",
                        "--no-edit",
                        task_branch,
                        "-m",
                        f"[{self.item_id}] merge {task_id} into {branch}",
                    ],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise WorktreeError(
                f"merge para {branch} falhou ({self.item_id}): {exc}"
            ) from exc
        return branch
