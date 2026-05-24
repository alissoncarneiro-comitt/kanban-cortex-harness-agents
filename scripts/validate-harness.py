#!/usr/bin/env python3
"""
Valida estrutura do Agent Harness Engineering Kanban.
Usage: python scripts/validate-harness.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_DIRS = [
    ".agents/skills",
    ".agents/kanban",
    ".agents/steering",
    ".agents/memory",
    "templates",
]

REQUIRED_SKILLS = [
    "00-steering",
    "10-discovery",
    "15-po",
    "20-spec",
    "30-design",
    "40-build",
    "50-review",
    "60-test",
    "70-ship",
    "80-governance",
]

REQUIRED_STEERING = [
    "product.md",
    "tech.md",
    "conventions.md",
    "structure.md",
    "decision-log.md",
]

REQUIRED_TEMPLATES = [
    "brief.md",
    "requirements.md",
    "design.md",
    "tasks.md",
    "steering-product.md",
    "decision-log.md",
]

FORBIDDEN_PATHS = [
    ".harness/kanban",
]

CLAUDE_SLASH_SKILLS = [
    "a-steering",
    "a-discover",
    "a-po",
    "a-spec",
    "a-design",
    "a-build",
    "a-review",
    "a-test",
    "a-ship",
    "a-governance",
]

CLAUDE_EXTRA_COMMANDS = [
    "a-replenish.md",
    "a-flow.md",
    "a-reflect.md",
    "a-plan.md",
]


def check_dir(path: Path, errors: list[str]) -> None:
    if not path.is_dir():
        errors.append(f"Diretório ausente: {path}")


def check_file(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"Arquivo ausente: {path}")


def validate_skill(skill_dir: Path, errors: list[str]) -> None:
    skill_md = skill_dir / "SKILL.md"
    check_file(skill_md, errors)
    if not skill_md.is_file():
        return

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        errors.append(f"Frontmatter YAML ausente em {skill_md}")
        return

    if ".harness/kanban" in content:
        errors.append(f"Path legado .harness/kanban em {skill_md} — use .agents/kanban/")


def validate_kanban_symlink(root: Path, errors: list[str]) -> None:
    kanban = root / "kanban"
    if kanban.is_symlink():
        target = kanban.resolve()
        expected = (root / ".agents/kanban").resolve()
        if target != expected:
            errors.append(f"Symlink kanban/ aponta para {target}, esperado {expected}")
    elif kanban.is_dir():
        board = kanban / "board.yaml"
        agents_board = root / ".agents/kanban/board.yaml"
        if board.exists() and agents_board.exists() and board.resolve() != agents_board.resolve():
            errors.append("kanban/board.yaml duplicado — use symlink kanban → .agents/kanban")


def main() -> int:
    root = Path.cwd()
    errors: list[str] = []

    for directory in REQUIRED_DIRS:
        check_dir(root / directory, errors)

    for skill in REQUIRED_SKILLS:
        validate_skill(root / ".agents/skills" / skill, errors)

    for doc in REQUIRED_STEERING:
        check_file(root / ".agents/steering" / doc, errors)

    for template in REQUIRED_TEMPLATES:
        check_file(root / "templates" / template, errors)

    check_file(root / ".agents/kanban/board.yaml", errors)
    check_file(root / "AGENTS.md", errors)
    check_file(root / "harness.yaml", errors)

    validate_kanban_symlink(root, errors)

    for slash in CLAUDE_SLASH_SKILLS:
        check_file(root / ".claude" / "skills" / slash / "SKILL.md", errors)

    for cmd in CLAUDE_EXTRA_COMMANDS:
        check_file(root / ".agents" / "commands" / cmd, errors)
        check_file(root / ".claude" / "commands" / cmd, errors)

    for forbidden in FORBIDDEN_PATHS:
        if (root / forbidden).exists():
            errors.append(f"Path legado encontrado: {forbidden}")

    if errors:
        print("❌ Validação falhou:\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("✅ Harness válido")
    print(f"   Skills: {len(REQUIRED_SKILLS)}")
    print(f"   Steering docs: {len(REQUIRED_STEERING)}")
    print(f"   Kanban: .agents/kanban/board.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
