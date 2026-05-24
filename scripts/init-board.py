#!/usr/bin/env python3
"""
Inicializa a estrutura Kanban do Agent Harness Engineering Kanban.
Usage: python scripts/init-board.py
"""
from pathlib import Path

KANBAN_ROOT = Path(".agents/kanban")

DIRS = [
    KANBAN_ROOT / "backlog",
    KANBAN_ROOT / "in-progress",
    KANBAN_ROOT / "done",
    KANBAN_ROOT / "reviews",
    KANBAN_ROOT / "daily-logs",
    Path(".agents/steering"),
    Path(".agents/memory"),
    Path(".agents/decisions"),
    Path("specs/active"),
    Path("specs/archive"),
    Path("docs/tutorial"),
    Path("docs/how-to"),
    Path("docs/reference"),
    Path("docs/explanation"),
    Path("docs/examples"),
    Path("tests/regression"),
]


def ensure_kanban_symlink() -> None:
    link = Path("kanban")
    if link.is_symlink():
        return
    if link.exists() and link.is_dir() and not any(link.iterdir()):
        link.rmdir()
    if not link.exists():
        link.symlink_to(".agents/kanban", target_is_directory=True)
        print("✅ kanban → .agents/kanban (symlink)")


def init() -> None:
    for directory in DIRS:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}")

        if directory.name != ".gitkeep" and not any(directory.iterdir()):
            (directory / ".gitkeep").touch()

    ensure_kanban_symlink()

    board = KANBAN_ROOT / "board.yaml"
    if not board.exists():
        print("⚠️  board.yaml ausente em .agents/kanban/ — copie do template do framework.")

    print("\n🚀 Agent Harness Engineering Kanban inicializado!")
    print("Próximo passo: /a-steering init ou edite AGENTS.md com a identidade do projeto.")


if __name__ == "__main__":
    init()
