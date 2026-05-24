#!/usr/bin/env python3
"""Validates board.yaml schema, WIP limits, locks, and orphans (read-only)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from enum import Enum
from typing import NamedTuple
from pathlib import Path
from typing import Callable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

DEFAULT_BOARD = Path(".agents/kanban/board.yaml")
DEFAULT_KANBAN_ROOT = Path(".agents/kanban")
DEFAULT_IN_PROGRESS = DEFAULT_KANBAN_ROOT / "in-progress"
DEFAULT_HEALTH_REPORT = DEFAULT_KANBAN_ROOT / "board-health.md"
PLAYBOOK_PATH = "docs/how-to/recover-board-state.md"
WIP_TOTAL_LIMIT = 10
NON_WIP_KEYS = {"backlog", "done"}
GIT_TIMEOUT = 10

LOCK_PATTERN = re.compile(
    r"LOCKED\s*[—\-]\s*approved\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

GitRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


class Severity(str, Enum):
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


class CheckResult(NamedTuple):
    name: str
    status: str
    detail: str


def column_name_to_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def playbook_ref(anchor: str) -> str:
    return f"see {PLAYBOOK_PATH}#{anchor}"


def load_board(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    if not path.is_file():
        raise FileNotFoundError(f"board.yaml not found: {path}")
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML") from exc
    if not isinstance(data, dict) or "board" not in data:
        raise ValueError("invalid board structure")
    return data


def count_items_by_column(board: dict) -> dict[str, int]:
    items = board.get("board", {}).get("items", {}) or {}
    counts: dict[str, int] = {}
    for key, value in items.items():
        if isinstance(value, list):
            counts[key] = len(value)
        else:
            counts[key] = 0
    return counts


def collect_board_item_ids(board: dict) -> set[str]:
    ids: set[str] = set()
    items = board.get("board", {}).get("items", {}) or {}
    for entries in items.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id"):
                ids.add(str(entry["id"]))
    return ids


def validate_wip(board: dict) -> list[str]:
    errors: list[str] = []
    columns = board.get("board", {}).get("columns", []) or []
    counts = count_items_by_column(board)

    total = sum(count for key, count in counts.items() if key not in NON_WIP_KEYS)
    if total > WIP_TOTAL_LIMIT:
        errors.append(
            f"HARNESS ERROR: WIP limit exceeded ({total}/{WIP_TOTAL_LIMIT}) "
            f"({playbook_ref('wip-overflow')})"
        )

    for column in columns:
        limit = column.get("wip_limit")
        if limit is None:
            continue
        key = column_name_to_key(column.get("name", ""))
        count = counts.get(key, 0)
        if count > limit:
            col_name = column.get("name", key)
            errors.append(
                f"HARNESS ERROR: column {col_name} WIP exceeded ({count}/{limit}) "
                f"({playbook_ref('wip-overflow')})"
            )
    return errors


def validate_board(path: Path) -> tuple[bool, list[str]]:
    try:
        board = load_board(path)
    except FileNotFoundError as exc:
        return False, [f"HARNESS ERROR: board.yaml not found ({exc})"]
    except ValueError:
        return (
            False,
            [
                f"HARNESS ERROR: board.yaml invalid YAML ({playbook_ref('yaml-invalido')})"
            ],
        )
    except RuntimeError as exc:
        return False, [str(exc)]

    errors = validate_wip(board)
    return len(errors) == 0, errors


def extract_lock_date(design_text: str) -> str | None:
    match = LOCK_PATTERN.search(design_text)
    return match.group(1) if match else None


def default_git_runner(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=False,
    )


GIT_LOCK_VERIFY_ERROR = "HARNESS ERROR: cannot verify lock — git unavailable"


def git_commits_after_lock(
    design_path: Path,
    lock_date: str,
    repo_root: Path,
    run_git: GitRunner | None = None,
) -> tuple[list[str] | None, str | None]:
    """Return (commits, None) on success; (None, error) when git cannot verify."""
    runner = run_git or default_git_runner
    try:
        rel = design_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None, GIT_LOCK_VERIFY_ERROR
    result = runner(
        [
            "git",
            "log",
            f"--after={lock_date}",
            "--format=%H",
            "-n",
            "1",
            "--",
            str(rel),
        ],
        repo_root,
    )
    if result.returncode != 0:
        return None, GIT_LOCK_VERIFY_ERROR
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return commits, None


def check_lock_for_item(
    item_id: str,
    in_progress_root: Path,
    repo_root: Path,
    run_git: GitRunner | None = None,
) -> str | None:
    design_path = in_progress_root / item_id / "design.md"
    if not design_path.is_file():
        return None
    text = design_path.read_text(encoding="utf-8")
    lock_date = extract_lock_date(text)
    if not lock_date:
        return None
    commits, git_err = git_commits_after_lock(design_path, lock_date, repo_root, run_git)
    if git_err:
        return f"{git_err} ({playbook_ref('lock-violation')})"
    if commits:
        return (
            f"LOCK VIOLATION: design.md for {item_id} modified after lock on {lock_date} "
            f"({playbook_ref('lock-violation')})"
        )
    return None


def check_locks(
    in_progress_root: Path,
    repo_root: Path,
    item_id: str | None = None,
    run_git: GitRunner | None = None,
) -> list[str]:
    errors: list[str] = []
    if item_id:
        msg = check_lock_for_item(item_id, in_progress_root, repo_root, run_git)
        if msg:
            errors.append(msg)
        return errors

    if not in_progress_root.is_dir():
        return errors

    for entry in sorted(in_progress_root.iterdir()):
        if entry.is_dir():
            msg = check_lock_for_item(entry.name, in_progress_root, repo_root, run_git)
            if msg:
                errors.append(msg)
    return errors


def list_feature_branches(
    repo_root: Path,
    run_git: GitRunner | None = None,
) -> list[str]:
    runner = run_git or default_git_runner
    result = runner(["git", "branch", "-a"], repo_root)
    if result.returncode != 0:
        return []

    branches: list[str] = []
    for line in result.stdout.splitlines():
        name = line.strip().lstrip("* ").strip()
        if name.startswith("remotes/"):
            name = name.split("/", 2)[-1] if name.count("/") >= 2 else name
        if name.startswith("feature/"):
            branches.append(name)
    return sorted(set(branches))


def feature_branch_item_id(branch: str) -> str | None:
    prefix = "feature/"
    if not branch.startswith(prefix):
        return None
    rest = branch[len(prefix) :]
    token = rest.split("/", 1)[0]
    if token.startswith("FEAT-"):
        return token
    return None


def check_orphan_branches(
    board_ids: set[str],
    repo_root: Path,
    run_git: GitRunner | None = None,
) -> list[str]:
    warnings: list[str] = []
    for branch in list_feature_branches(repo_root, run_git):
        item_id = feature_branch_item_id(branch)
        if item_id and item_id not in board_ids:
            short = branch.replace("feature/", "", 1)
            warnings.append(
                f"ORPHAN BRANCH: feature/{short} ({playbook_ref('orphan-branch')})"
            )
    return warnings


def check_orphan_items(
    board_ids: set[str],
    in_progress_root: Path,
) -> list[str]:
    warnings: list[str] = []
    if not in_progress_root.is_dir():
        return warnings
    for entry in sorted(in_progress_root.iterdir()):
        if entry.is_dir() and entry.name not in board_ids:
            warnings.append(
                f"WARNING: orphan item {entry.name} ({playbook_ref('orphan-item')})"
            )
    return warnings


def run_full_checks(
    board_path: Path,
    kanban_root: Path,
    repo_root: Path,
    run_git: GitRunner | None = None,
) -> tuple[list[CheckResult], int]:
    results: list[CheckResult] = []
    exit_code = 0
    in_progress = kanban_root / "in-progress"

    try:
        board = load_board(board_path)
        yaml_ok = True
    except FileNotFoundError as exc:
        results.append(
            CheckResult(
                "YAML válido", Severity.ERROR.value, f"board.yaml not found: {exc}"
            )
        )
        return results, 1
    except ValueError:
        results.append(
            CheckResult(
                "YAML válido",
                Severity.ERROR.value,
                f"invalid YAML ({playbook_ref('yaml-invalido')})",
            )
        )
        return results, 1
    except RuntimeError as exc:
        results.append(CheckResult("YAML válido", Severity.ERROR.value, str(exc)))
        return results, 1

    results.append(CheckResult("YAML válido", Severity.OK.value, "parse OK"))

    wip_errors = validate_wip(board)
    if wip_errors:
        results.append(
            CheckResult("WIP limits", Severity.ERROR.value, "; ".join(wip_errors))
        )
        exit_code = 1
    else:
        results.append(CheckResult("WIP limits", Severity.OK.value, "within limits"))

    lock_errors = check_locks(in_progress, repo_root, run_git=run_git)
    if lock_errors:
        results.append(
            CheckResult(
                "Lock violations", Severity.ERROR.value, "; ".join(lock_errors)
            )
        )
        exit_code = 1
    else:
        results.append(
            CheckResult("Lock violations", Severity.OK.value, "no violations")
        )

    board_ids = collect_board_item_ids(board)
    orphan_branch_msgs = check_orphan_branches(board_ids, repo_root, run_git)
    if orphan_branch_msgs:
        results.append(
            CheckResult(
                "Orphan branches",
                Severity.WARN.value,
                "; ".join(orphan_branch_msgs),
            )
        )
    else:
        results.append(CheckResult("Orphan branches", Severity.OK.value, "none"))

    orphan_item_msgs = check_orphan_items(board_ids, in_progress)
    if orphan_item_msgs:
        results.append(
            CheckResult(
                "Orphan items", Severity.WARN.value, "; ".join(orphan_item_msgs)
            )
        )
    else:
        results.append(CheckResult("Orphan items", Severity.OK.value, "none"))

    return results, exit_code


def write_health_report(path: Path, results: list[CheckResult]) -> None:
    lines = [
        "# Board Health Report",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for row in results:
        detail = row.detail.replace("|", "\\|")
        lines.append(f"| {row.name} | {row.status} | {detail} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate harness board.yaml")
    parser.add_argument(
        "--board",
        default=str(DEFAULT_BOARD),
        help="Path to board.yaml (default: .agents/kanban/board.yaml)",
    )
    parser.add_argument(
        "--kanban-root",
        default=str(DEFAULT_KANBAN_ROOT),
        help="Kanban root directory (default: .agents/kanban)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root for git checks (default: .)",
    )
    parser.add_argument(
        "--item",
        metavar="ID",
        help="Run lock check for a single item (e.g. FEAT-004)",
    )
    parser.add_argument(
        "--check-locks",
        action="store_true",
        help="Check design.md lock violations for all in-progress items",
    )
    parser.add_argument(
        "--check-orphan-branches",
        action="store_true",
        help="List feature/* branches without a board.yaml item (warnings only)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all checks and write board-health.md",
    )
    parser.add_argument(
        "--health-report",
        default=str(DEFAULT_HEALTH_REPORT),
        help="Output path for --full report",
    )
    args = parser.parse_args(argv)

    board_path = Path(args.board)
    kanban_root = Path(args.kanban_root)
    repo_root = Path(args.repo_root)
    in_progress = kanban_root / "in-progress"

    if args.full:
        results, code = run_full_checks(board_path, kanban_root, repo_root)
        write_health_report(Path(args.health_report), results)
        for row in results:
            if row.status == Severity.ERROR.value:
                print(row.detail, file=sys.stderr)
            elif row.status == Severity.WARN.value:
                print(row.detail)
        if code == 0:
            print(f"OK: board health report → {args.health_report}")
        return code

    if args.check_orphan_branches:
        try:
            board = load_board(board_path)
        except (FileNotFoundError, ValueError, RuntimeError):
            print(
                f"HARNESS ERROR: cannot load board.yaml ({playbook_ref('yaml-invalido')})",
                file=sys.stderr,
            )
            return 1
        board_ids = collect_board_item_ids(board)
        for msg in check_orphan_branches(board_ids, repo_root):
            print(msg)
        for msg in check_orphan_items(board_ids, in_progress):
            print(msg)
        return 0

    if args.check_locks and not args.item:
        lock_errors = check_locks(in_progress, repo_root)
        if lock_errors:
            for message in lock_errors:
                print(message, file=sys.stderr)
            return 1
        print("OK: no lock violations")
        return 0

    ok, messages = validate_board(board_path)
    if not ok:
        for message in messages:
            print(message, file=sys.stderr)
        return 1

    if args.item:
        lock_errors = check_locks(in_progress, repo_root, item_id=args.item)
        if lock_errors:
            for message in lock_errors:
                print(message, file=sys.stderr)
            return 1
        print(f"OK: board.yaml valid; no lock violations for {args.item}")
        return 0

    print("OK: board.yaml valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
