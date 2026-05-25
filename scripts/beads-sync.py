#!/usr/bin/env python3
"""
beads-sync.py — Sync tasks.md entries to Beads issue tracker.

Reads harness.yaml to check integrations.beads.enabled.
If enabled, creates one Beads issue per TASK-NNN found in tasks.md,
stores the bd_id back into task.yaml, and links dependencies via bd dep add.

Exits 0 always — graceful degradation when Beads is unavailable.

Usage:
    python scripts/beads-sync.py --item FEAT-017 \
        --tasks .agents/kanban/in-progress/FEAT-017/tasks.md \
        --task-yaml .agents/kanban/in-progress/FEAT-017/task.yaml
"""

import argparse
import re
import subprocess
import sys
import os

try:
    import yaml
except ImportError:
    yaml = None


def _load_yaml(path):
    if yaml is None:
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_yaml(path, data):
    if yaml is None:
        return
    try:
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    except Exception:
        pass


def _beads_enabled(harness_yaml_path="harness.yaml"):
    """Return True if integrations.beads.enabled is true in harness.yaml."""
    for candidate in [harness_yaml_path, "kanban-cortex-harness-agents/harness.yaml"]:
        data = _load_yaml(candidate)
        if data:
            try:
                return bool(data["integrations"]["beads"]["enabled"])
            except (KeyError, TypeError):
                pass
    return False


def _bd_available():
    """Return True if the bd CLI is on PATH."""
    try:
        result = subprocess.run(
            ["bd", "--version"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _bd_create(title, description="", item_id="", task_id=""):
    """Create a Beads issue and return its ID string, or empty string on failure."""
    desc = description or f"Task {task_id} for {item_id}"
    try:
        result = subprocess.run(
            ["bd", "q", title, "--type", "task", "--priority", "2"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            bd_id = result.stdout.strip()
            if bd_id:
                if description:
                    subprocess.run(
                        ["bd", "update", bd_id, "--description", desc],
                        capture_output=True,
                        timeout=10,
                    )
                return bd_id
    except Exception:
        pass
    return ""


def _bd_dep_add(blocked_bd_id, blocker_bd_id):
    """Add dependency: blocked_bd_id depends on blocker_bd_id (blocker blocks blocked)."""
    try:
        subprocess.run(
            ["bd", "dep", "add", blocked_bd_id, blocker_bd_id],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def _parse_tasks(tasks_md_path):
    """
    Parse tasks.md and return list of dicts:
        [{"id": "TASK-001", "title": "...", "depends": ["TASK-002", ...]}]
    """
    try:
        with open(tasks_md_path) as f:
            content = f.read()
    except FileNotFoundError:
        return []

    tasks = []
    # Match ## TASK-NNN: title
    for m in re.finditer(r"^##\s+(TASK-\d+):\s*(.+)$", content, re.MULTILINE):
        task_id = m.group(1)
        title = m.group(2).strip()
        # Find _Depends_: line in the next ~10 lines after this heading
        after = content[m.end():]
        depends = []
        dep_match = re.search(r"_Depends_:\s*(.+)", after[:500])
        if dep_match:
            dep_raw = dep_match.group(1).strip()
            if dep_raw.lower() not in ("none", "nenhum", "nenhuma", "-", ""):
                depends = [t.strip() for t in re.split(r"[,;]+", dep_raw) if t.strip()]
        tasks.append({"id": task_id, "title": title, "depends": depends})

    return tasks


def main():
    parser = argparse.ArgumentParser(description="Sync tasks.md to Beads")
    parser.add_argument("--item", required=True, help="Item ID (e.g., FEAT-017)")
    parser.add_argument("--tasks", required=True, help="Path to tasks.md")
    parser.add_argument(
        "--task-yaml",
        help="Path to task.yaml (auto-derived from --tasks if omitted)",
    )
    parser.add_argument(
        "--harness",
        default="harness.yaml",
        help="Path to harness.yaml",
    )
    args = parser.parse_args()

    task_yaml_path = args.task_yaml or os.path.join(
        os.path.dirname(args.tasks), "task.yaml"
    )

    if not _beads_enabled(args.harness):
        print("[beads-sync] integrations.beads.enabled=false — skipping", file=sys.stderr)
        return

    if not _bd_available():
        print("[beads-sync] bd CLI not found — skipping gracefully", file=sys.stderr)
        return

    tasks = _parse_tasks(args.tasks)
    if not tasks:
        print(f"[beads-sync] No TASK-NNN entries found in {args.tasks}", file=sys.stderr)
        return

    task_yaml = _load_yaml(task_yaml_path)
    if "beads" not in task_yaml:
        task_yaml["beads"] = {"enabled": True, "tasks": {}}
    if "tasks" not in task_yaml["beads"]:
        task_yaml["beads"]["tasks"] = {}

    task_to_bd = {}

    for task in tasks:
        task_id = task["id"]
        existing = task_yaml["beads"]["tasks"].get(task_id, {})
        if existing.get("bd_id"):
            task_to_bd[task_id] = existing["bd_id"]
            print(f"[beads-sync] {task_id} already has bd_id={existing['bd_id']}")
            continue

        title = f"{args.item} {task_id}: {task['title']}"
        bd_id = _bd_create(
            title=title,
            description=f"Implementation task {task_id} for {args.item}. See tasks.md for boundary and acceptance criteria.",
            item_id=args.item,
            task_id=task_id,
        )
        if bd_id:
            task_yaml["beads"]["tasks"][task_id] = {
                "bd_id": bd_id,
                "title": task["title"],
            }
            task_to_bd[task_id] = bd_id
            print(f"[beads-sync] Created {task_id} → {bd_id}")
        else:
            print(f"[beads-sync] Failed to create Beads issue for {task_id}", file=sys.stderr)

    _save_yaml(task_yaml_path, task_yaml)

    # Link dependencies
    for task in tasks:
        blocked_id = task["id"]
        blocked_bd = task_to_bd.get(blocked_id)
        if not blocked_bd:
            continue
        for dep_task_id in task["depends"]:
            blocker_bd = task_to_bd.get(dep_task_id)
            if blocker_bd:
                _bd_dep_add(blocked_bd, blocker_bd)
                print(f"[beads-sync] dep: {blocked_id}({blocked_bd}) depends on {dep_task_id}({blocker_bd})")
            else:
                print(f"[beads-sync] Warning: dependency {dep_task_id} has no bd_id — skipping link", file=sys.stderr)

    print(f"[beads-sync] Done. {len(task_to_bd)} task(s) synced to Beads.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[beads-sync] Unexpected error (non-fatal): {e}", file=sys.stderr)
        sys.exit(0)
