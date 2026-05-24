#!/usr/bin/env python3
"""Verifica se arquivos modificados respeitam boundaries declarados em tasks.md."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TASK_SECTION_RE = re.compile(r"^## TASK-(\d+):", re.MULTILINE)
BOUNDARY_RE = re.compile(r"^\s*_Boundary_:\s*(.+)$", re.MULTILINE)
DIFF_GIT_RE = re.compile(r"^diff --git a/.+ b/(.+)$")


def extract_paths_from_boundary(raw: str) -> list[str]:
    parts = re.split(r"\s*\+\s*", raw.strip())
    paths: list[str] = []
    for part in parts:
        cleaned = part.strip().strip("`'\"")
        if cleaned:
            paths.append(cleaned)
    return paths


def parse_tasks_boundaries(content: str) -> list[tuple[str, list[str]]]:
    tasks: list[tuple[str, list[str]]] = []
    sections = re.split(r"(?=^## TASK-\d+:)", content, flags=re.MULTILINE)
    for section in sections:
        match = TASK_SECTION_RE.search(section)
        if not match:
            continue
        task_id = f"TASK-{match.group(1)}"
        boundary_match = BOUNDARY_RE.search(section)
        if not boundary_match:
            tasks.append((task_id, []))
            continue
        paths = extract_paths_from_boundary(boundary_match.group(1))
        tasks.append((task_id, paths))
    return tasks


def file_matches_boundary(file_path: str, boundary: str) -> bool:
    boundary = boundary.strip().strip("`'\"")
    if not boundary:
        return False
    if file_path == boundary:
        return True
    if boundary.endswith("/"):
        prefix = boundary.rstrip("/")
        return file_path == prefix or file_path.startswith(prefix + "/")
    if file_path.startswith(boundary + "/"):
        return True
    # directory boundary without trailing slash (e.g. src/features/auth)
    if "/" in boundary and not Path(boundary).suffix:
        prefix = boundary.rstrip("/")
        return file_path == prefix or file_path.startswith(prefix + "/")
    return False


def parse_diff_file_names(content: str) -> list[str]:
    files: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("+++ b/"):
            path = stripped[6:]
            if path != "/dev/null":
                files.append(path)
            continue
        git_match = DIFF_GIT_RE.match(stripped)
        if git_match:
            files.append(git_match.group(1))
            continue
        if stripped.startswith(("---", "+++", "@@", "index ", "\\")):
            continue
        if stripped.startswith(("+", "-")) and not stripped.startswith(("+++", "---")):
            continue
        if "/" in stripped or "." in stripped:
            files.append(stripped.lstrip("+-"))
    seen: set[str] = set()
    ordered: list[str] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def get_changed_files_from_git(branch: str, base: str = "main") -> list[str]:
    result = subprocess.run(
        ["git", "diff", f"{base}..{branch}", "--name-only"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def find_covering_task(
    file_path: str, tasks: list[tuple[str, list[str]]]
) -> tuple[str | None, list[str]]:
    for task_id, boundaries in tasks:
        for boundary in boundaries:
            if file_matches_boundary(file_path, boundary):
                return task_id, boundaries
    return None, tasks[0][1] if tasks else []


def check_boundaries(
    tasks_content: str, changed_files: list[str]
) -> list[str]:
    tasks = parse_tasks_boundaries(tasks_content)
    if not tasks_content.strip():
        raise ValueError("tasks.md is empty")
    if not tasks:
        raise ValueError("tasks.md has no TASK sections")

    violations: list[str] = []
    for file_path in changed_files:
        task_id, boundaries = find_covering_task(file_path, tasks)
        if task_id is None:
            violations.append(
                f"VIOLATION: unscoped file {file_path} "
                f"(not covered by any task _Boundary_ in tasks.md)"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Boundary checker for harness tasks.md")
    parser.add_argument("--tasks", required=True, help="Path to tasks.md")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--branch", help="Git branch to diff against main")
    group.add_argument("--diff", dest="diff_file", help="Path to diff or name-only file list")
    parser.add_argument("--base", default="main", help="Base branch for git diff (default: main)")
    args = parser.parse_args(argv)

    tasks_path = Path(args.tasks)
    if not tasks_path.is_file():
        print(f"ERROR: tasks file not found: {tasks_path}", file=sys.stderr)
        return 2

    try:
        tasks_content = tasks_path.read_text(encoding="utf-8")
        if args.diff_file:
            diff_path = Path(args.diff_file)
            if not diff_path.is_file():
                print(f"ERROR: diff file not found: {diff_path}", file=sys.stderr)
                return 2
            changed_files = parse_diff_file_names(diff_path.read_text(encoding="utf-8"))
        else:
            changed_files = get_changed_files_from_git(args.branch, base=args.base)

        violations = check_boundaries(tasks_content, changed_files)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if violations:
        for line in violations:
            print(line)
        return 1

    print("PASS: no boundary violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
