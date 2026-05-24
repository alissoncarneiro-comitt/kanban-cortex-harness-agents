#!/usr/bin/env python3
"""
pipeline.py — orquestrador fire-and-forget entre skills do Agent Harness.

FEAT-007 TASK-001.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from orchestrator import invoke_registry, task_dag, worktree

BASE_DIR = "."
PIPELINE_CONFIG = ".agents/config/pipeline.yaml"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_yaml_path(item_id: str, base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir if base_dir is not None else BASE_DIR)
    candidates = [
        root / "in-progress" / item_id / "task.yaml",
        root / ".agents" / "kanban" / "in-progress" / item_id / "task.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def _write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle, default_flow_style=False, allow_unicode=True)


def _read_task(item_id: str, base_dir: str | Path | None = None) -> tuple[dict, Path]:
    path = _task_yaml_path(item_id, base_dir)
    if not path.exists():
        raise FileNotFoundError(f"task.yaml não encontrado: {path}")
    data = _load_yaml(path)
    _ensure_sections(data)
    return data, path


def _ensure_sections(data: dict) -> None:
    data.setdefault("pipeline", {})
    pipeline = data["pipeline"]
    pipeline.setdefault("status", "idle")
    pipeline.setdefault("current_phase", None)
    pipeline.setdefault("rejection_count", 0)
    pipeline.setdefault("error", "")
    pipeline.setdefault("started_at", None)
    pipeline.setdefault("last_updated", None)
    pipeline.setdefault("adapter_used", None)
    pipeline.setdefault("current_task", None)
    pipeline.setdefault("handoff_missing_phase", None)

    data.setdefault("phase_sessions", {})
    for phase in ("build", "review", "test", "ship"):
        data["phase_sessions"].setdefault(phase, None)

    data.setdefault("phase_status", {})
    for phase in ("build", "review", "test", "ship"):
        data["phase_status"].setdefault(phase, None)


def _config() -> dict:
    path = Path(PIPELINE_CONFIG)
    if not path.exists():
        path = Path(BASE_DIR) / ".agents" / "config" / "pipeline.yaml"
    if not path.exists():
        return {
            "pipeline": {
                "retry_limit": 2,
                "phase_timeout_minutes": 60,
                "poll_interval_seconds": 5,
                "phases": [],
            }
        }
    return _load_yaml(path)


def _phase_config(phase: str) -> dict:
    cfg = _config().get("pipeline", {})
    for entry in cfg.get("phases", []):
        if entry.get("name") == phase:
            return entry
    defaults = {
        "build": ".agents/skills/40-build/SKILL.md",
        "review": ".agents/skills/50-review/SKILL.md",
        "test": ".agents/skills/60-test/SKILL.md",
        "ship": ".agents/skills/70-ship/SKILL.md",
    }
    return {"name": phase, "skill_file": defaults[phase]}


def _log(item_id: str, message: str, base_dir: str | Path | None = None) -> None:
    try:
        task_path = _task_yaml_path(item_id, base_dir)
        log_path = task_path.parent / "pipeline.log"
        line = f"{_now_iso()} {message}\n"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def _set_pipeline(
    item_id: str,
    *,
    status: Optional[str] = None,
    current_phase: Optional[str] = None,
    error: Optional[str] = None,
    base_dir: str | Path | None = None,
) -> dict:
    data, path = _read_task(item_id, base_dir)
    pipeline = data["pipeline"]
    if status is not None:
        pipeline["status"] = status
    if current_phase is not None:
        pipeline["current_phase"] = current_phase
    if error is not None:
        pipeline["error"] = error
    if pipeline.get("started_at") is None and status == "running":
        pipeline["started_at"] = _now_iso()
    pipeline["last_updated"] = _now_iso()
    _write_yaml(path, data)
    return data


def _update_task_status(
    item_id: str,
    task_id: str,
    status: str,
    base_dir: str | Path | None = None,
) -> None:
    """Write per-task status to task.yaml tasks: list and task_progress."""
    data, path = _read_task(item_id, base_dir)
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
        data["tasks"] = tasks
    for entry in tasks:
        if isinstance(entry, dict) and entry.get("id") == task_id:
            entry["status"] = status
            break
    else:
        tasks.append({"id": task_id, "status": status})
    data.setdefault("task_progress", {})
    if not isinstance(data["task_progress"], dict):
        data["task_progress"] = {}
    progress_status = status
    if status == "in_progress":
        progress_status = "running"
    data["task_progress"][task_id] = progress_status
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _tasks_md_path(item_id: str, base_dir: str | Path | None = None) -> Path:
    return _task_yaml_path(item_id, base_dir).parent / "tasks.md"


def _init_task_progress(
    item_id: str,
    graph: dict[str, list[str]],
    base_dir: str | Path | None = None,
) -> None:
    data, path = _read_task(item_id, base_dir)
    data.setdefault("task_progress", {})
    if not isinstance(data["task_progress"], dict):
        data["task_progress"] = {}
    for task_id in graph:
        data["task_progress"].setdefault(task_id, "pending")
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _set_build_phase_done(item_id: str, base_dir: str | Path | None = None) -> None:
    data, path = _read_task(item_id, base_dir)
    data["phase_status"]["build"] = "done"
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _clear_phase_status(item_id: str, phase: str, base_dir: str | Path | None = None) -> None:
    data, path = _read_task(item_id, base_dir)
    data["phase_status"][phase] = None
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _handoff_packet_path(item_id: str, base_dir: str | Path | None = None) -> Path:
    return _task_yaml_path(item_id, base_dir).parent / "handoff-packet.yaml"


def is_pipeline_retry(item_id: str, base_dir: str | Path | None = None) -> bool:
    """True se rebuild após review changes_requested (FEAT-011 TASK-006)."""
    path = _handoff_packet_path(item_id, base_dir)
    if not path.exists():
        return False
    packet = _load_yaml(path)
    return bool(packet.get("pipeline_retry"))


def prepare_build_retry(item_id: str, base_dir: str | Path | None = None) -> None:
    """Marca handoff-packet para rebuild: pipeline_retry + review-feedback.md (TASK-006)."""
    base = base_dir if base_dir is not None else BASE_DIR
    packet_path = _handoff_packet_path(item_id, base)
    packet: dict[str, Any] = {}
    if packet_path.exists():
        packet = _load_yaml(packet_path)
    packet["pipeline_retry"] = True
    packet["to_phase"] = "build"
    packet.setdefault("item", item_id)
    allowed = list(packet.get("artifacts_allowed") or [])
    for entry in (
        "design.md",
        "tasks.md",
        ".agents/steering/conventions.md",
        "review-feedback.md",
    ):
        if entry not in allowed:
            allowed.append(entry)
    packet["artifacts_allowed"] = [a for a in allowed if a != "review-report.md"]
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(packet_path, packet)
    _log(item_id, "pipeline_retry prepared for build", base)


def _task_dag_enabled(cfg: dict[str, Any] | None = None) -> bool:
    pipeline_cfg = cfg if cfg is not None else _config().get("pipeline", {})
    task_dag = pipeline_cfg.get("task_dag", {})
    if not isinstance(task_dag, dict):
        return False
    return bool(task_dag.get("enabled", False))


def record_phase_session(
    item_id: str,
    phase: str,
    base_dir: str | Path | None = None,
) -> str:
    """Grava UUID único em phase_sessions.{phase} no início de cada fase (REQ-002)."""
    data, path = _read_task(item_id, base_dir)
    session_id = str(uuid.uuid4())
    data.setdefault("phase_sessions", {})
    data["phase_sessions"][phase] = session_id
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)
    return session_id


def _record_phase_session(
    item_id: str,
    phase: str,
    base_dir: str | Path | None = None,
) -> str:
    return record_phase_session(item_id, phase, base_dir)


def _set_pipeline_adapter(
    item_id: str,
    adapter_name: str,
    base_dir: str | Path | None = None,
) -> None:
    data, path = _read_task(item_id, base_dir)
    data["pipeline"]["adapter_used"] = adapter_name
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _gate_approved(data: dict, gate: str) -> bool:
    gates = data.get("gates", {})
    if not isinstance(gates, dict):
        return False
    value = gates.get(gate, {})
    return isinstance(value, dict) and value.get("approved") is True


def _handoff_required(cfg: dict) -> bool:
    handoff = cfg.get("handoff", {})
    if not isinstance(handoff, dict):
        return False
    return bool(handoff.get("required", False))


def _missing_handoff_error(cfg: dict) -> bool:
    handoff = cfg.get("handoff", {})
    if not isinstance(handoff, dict):
        return True
    return bool(handoff.get("missing_handoff_error", True))


def _set_handoff_missing_error(
    item_id: str,
    phase: str,
    base_dir: str | Path,
    *,
    task_id: str | None = None,
) -> None:
    """REQ-004: erro explícito quando handoff obrigatório não ocorre antes do timeout."""
    message = f"handoff ausente na fase {phase}"
    if task_id:
        message = f"handoff ausente na fase {phase} (task {task_id})"
    data, path = _read_task(item_id, base_dir)
    pipeline = data["pipeline"]
    pipeline["status"] = "error"
    pipeline["error"] = message
    pipeline["handoff_missing_phase"] = phase
    pipeline["last_updated"] = _now_iso()
    _write_yaml(path, data)
    _log(item_id, f"handoff_missing phase={phase} task={task_id or ''}", base_dir)
    print(
        f"[pipeline] {message} para {item_id}. Execute handoff.py --item {item_id} --phase {phase}.",
        file=sys.stderr,
    )


def _invoke_skill(
    skill_file: str | Path,
    item: str,
    base_dir: str | Path = BASE_DIR,
    *,
    task_id: str | None = None,
    cwd: str | Path | None = None,
) -> int:
    """Invoca skill via invoke_registry (FEAT-011 TASK-002)."""
    pipeline_cfg = _config().get("pipeline", {})
    try:
        adapter = invoke_registry.resolve_adapter(pipeline_cfg)
        _set_pipeline_adapter(item, adapter.name, base_dir)
    except invoke_registry.AdapterNotFoundError:
        pass
    return invoke_registry.invoke_skill(
        skill_file,
        item,
        base_dir,
        task_id=task_id,
        pipeline_config=pipeline_cfg,
        cwd=cwd,
    )


def _poll_until_task_done(
    item_id: str,
    task_id: str,
    base_dir: str | Path,
    timeout_minutes: int = 60,
    poll_interval: int = 5,
) -> str:
    """Aguarda task_progress[TASK] via handoff --task (FEAT-011 TASK-008)."""
    deadline = time.time() + (timeout_minutes * 60)
    while time.time() < deadline:
        data, _ = _read_task(item_id, base_dir)
        if data["pipeline"].get("status") == "paused":
            return "paused"
        progress = data.get("task_progress", {})
        if isinstance(progress, dict):
            state = progress.get(task_id)
            if state in ("done", "failed"):
                return state
        time.sleep(poll_interval)
    return "timeout"


def _poll_until_phase_done(
    item_id: str,
    phase: str,
    base_dir: str | Path,
    timeout_minutes: int = 60,
    poll_interval: int = 5,
) -> str:
    deadline = time.time() + (timeout_minutes * 60)
    while time.time() < deadline:
        data, _ = _read_task(item_id, base_dir)
        if data["pipeline"].get("status") == "paused":
            return "paused"
        value = data.get("phase_status", {}).get(phase)
        if value:
            return value
        time.sleep(poll_interval)
    return "timeout"


def _run_phase(
    item_id: str,
    phase: str,
    base_dir: str | Path,
    cfg: dict,
    *,
    task_id: str | None = None,
    invoke_base_dir: str | Path | None = None,
) -> str:
    phase_cfg = _phase_config(phase)
    skill_file = phase_cfg["skill_file"]
    invoke_root = invoke_base_dir if invoke_base_dir is not None else base_dir
    _set_pipeline(item_id, status="running", current_phase=phase, base_dir=base_dir)
    session_id = _record_phase_session(item_id, phase, base_dir)
    _log(item_id, f"phase_start {phase} session={session_id}", base_dir)
    if task_id and _task_dag_enabled(cfg):
        data, path = _read_task(item_id, base_dir)
        data["pipeline"]["current_task"] = task_id
        data["pipeline"]["last_updated"] = _now_iso()
        _write_yaml(path, data)
    if task_id:
        _update_task_status(item_id, task_id, "in_progress", base_dir)
    _clear_phase_status(item_id, phase, base_dir)
    try:
        if task_id:
            exit_code = _invoke_skill(
                skill_file,
                item_id,
                base_dir,
                task_id=task_id,
                cwd=invoke_root,
            )
        else:
            exit_code = _invoke_skill(skill_file, item_id, base_dir, cwd=invoke_root)
    except Exception as exc:
        if task_id:
            _update_task_status(item_id, task_id, "error", base_dir)
        _set_pipeline(item_id, status="error", error=str(exc), base_dir=base_dir)
        _log(item_id, f"phase_error {phase}: {exc}", base_dir)
        return "error"
    if exit_code != 0:
        if task_id:
            _update_task_status(item_id, task_id, "error", base_dir)
        _set_pipeline(item_id, status="error", error=f"{phase} exit code {exit_code}", base_dir=base_dir)
        _log(item_id, f"phase_exit_nonzero {phase}: {exit_code}", base_dir)
        return "error"
    if task_id:
        result = _poll_until_task_done(
            item_id,
            task_id,
            base_dir,
            timeout_minutes=cfg.get("phase_timeout_minutes", 60),
            poll_interval=cfg.get("poll_interval_seconds", 5),
        )
    else:
        result = _poll_until_phase_done(
            item_id,
            phase,
            base_dir,
            timeout_minutes=cfg.get("phase_timeout_minutes", 60),
            poll_interval=cfg.get("poll_interval_seconds", 5),
        )
    _log(item_id, f"phase_result {phase}: {result}", base_dir)
    if result == "timeout":
        if task_id:
            _update_task_status(item_id, task_id, "error", base_dir)
        if _handoff_required(cfg) and _missing_handoff_error(cfg):
            _set_handoff_missing_error(item_id, phase, base_dir, task_id=task_id)
        else:
            _set_pipeline(item_id, status="error", error=f"timeout em {phase}", base_dir=base_dir)
        return "error"
    if task_id:
        if result == "failed":
            _update_task_status(item_id, task_id, "error", base_dir)
            return "error"
        if result == "done":
            _update_task_status(item_id, task_id, "done", base_dir)
    return result


def _run_single_task_build(
    item_id: str,
    task_id: str,
    base_dir: str | Path,
    cfg: dict,
    wt: worktree.WorktreeManager,
) -> str:
    """Build uma task em worktree dedicado."""
    try:
        path = wt.create(task_id)
        _log(item_id, f"worktree {task_id} -> {path}", base_dir)
    except worktree.WorktreeError as exc:
        return f"worktree_error:{exc}"
    return _run_phase(item_id, "build", base_dir, cfg, task_id=task_id, invoke_base_dir=path)


def _run_build_phase(
    item_id: str,
    base_dir: str | Path,
    cfg: dict,
) -> str:
    """Build legado (uma invocação) ou DAG paralelo com worktrees (TASK-008)."""
    if not _task_dag_enabled(cfg):
        return _run_phase(item_id, "build", base_dir, cfg)

    tasks_path = _tasks_md_path(item_id, base_dir)
    if not tasks_path.exists():
        _set_pipeline(
            item_id,
            status="error",
            error=f"tasks.md ausente: {tasks_path}",
            base_dir=base_dir,
        )
        return "error"

    try:
        graph = task_dag.parse_tasks_md(tasks_path)
    except task_dag.TaskDagError as exc:
        _set_pipeline(item_id, status="error", error=str(exc), base_dir=base_dir)
        return "error"

    max_parallel = max(1, int(cfg.get("max_parallel_tasks", 2)))
    repo_root = Path(base_dir if base_dir else BASE_DIR)
    wt = worktree.WorktreeManager(repo_root, item_id)
    _init_task_progress(item_id, graph, base_dir)
    _set_pipeline(item_id, status="running", current_phase="build", base_dir=base_dir)
    _record_phase_session(item_id, "build", base_dir)

    progress: set[str] = set()
    completed_order: list[str] = []

    while len(progress) < len(graph):
        ready = task_dag.ready_tasks(graph, progress)
        if not ready:
            _set_pipeline(
                item_id,
                status="error",
                error="DAG sem tasks prontas (deadlock ou falha anterior)",
                base_dir=base_dir,
            )
            return "error"

        wave = ready[:max_parallel]
        _log(item_id, f"dag_wave {wave}", base_dir)

        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = {
                pool.submit(
                    _run_single_task_build,
                    item_id,
                    tid,
                    base_dir,
                    cfg,
                    wt,
                ): tid
                for tid in wave
            }
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = f"error:{exc}"
                if result != "done":
                    _set_pipeline(
                        item_id,
                        status="error",
                        error=f"build falhou em {tid}: {result}",
                        base_dir=base_dir,
                    )
                    return "error"
                progress.add(tid)
                completed_order.append(tid)

    try:
        integration = wt.merge_to_integration(completed_order)
        _log(item_id, f"merged to {integration}", base_dir)
    except worktree.WorktreeError as exc:
        _set_pipeline(
            item_id,
            status="error",
            error=f"merge integração falhou: {exc}",
            base_dir=base_dir,
        )
        return "error"

    _set_build_phase_done(item_id, base_dir)
    _log(item_id, "build_phase_done after DAG merge", base_dir)
    return "done"


def run(item_id: str, base_dir: str | Path | None = None) -> str:
    base = str(base_dir if base_dir is not None else BASE_DIR)
    cfg = _config().get("pipeline", {})
    data, _ = _read_task(item_id, base)
    if data["pipeline"].get("status") == "running":
        _log(item_id, "already_running", base)
        return "already_running"
    if not _gate_approved(data, "tasks"):
        _log(item_id, "tasks_gate_not_approved", base)
        print(f"[pipeline] Gate de tasks não aprovado para {item_id}.", file=sys.stderr)
        return "tasks_gate_not_approved"

    if os.environ.get("PIPELINE_ENABLED", "").lower() not in ("1", "true", "yes"):
        print("[pipeline] PIPELINE_ENABLED não definido; continuando em modo build.", file=sys.stderr)

    _set_pipeline(item_id, status="running", current_phase="build", base_dir=base)
    _log(item_id, "pipeline_start", base)

    while True:
        result = _run_build_phase(item_id, base, cfg)
        if result != "done":
            return result

        result = _run_phase(item_id, "review", base, cfg)
        if result == "approved":
            break
        if result in ("changes_requested", "rejected"):
            data, _ = _read_task(item_id, base)
            count = int(data["pipeline"].get("rejection_count", 0))
            if count >= int(cfg.get("retry_limit", 2)):
                _set_pipeline(item_id, status="escalated", current_phase="review", base_dir=base)
                _log(item_id, "pipeline_escalated", base)
                return "escalated"
            prepare_build_retry(item_id, base)
            continue
        return result

    result = _run_phase(item_id, "test", base, cfg)
    if result == "passed":
        _set_pipeline(item_id, status="awaiting_ship_approval", current_phase="ship", base_dir=base)
        _log(item_id, "awaiting_ship_approval", base)
        print(f"[pipeline] QA verde. Execute /a-steering approve ship {item_id}")
        return "awaiting_ship_approval"
    if result == "failed":
        _set_pipeline(item_id, status="error", error="test failed", base_dir=base)
        return "error"
    return result


def pause(item_id: str, base_dir: str | Path | None = None) -> str:
    base = str(base_dir if base_dir is not None else BASE_DIR)
    _set_pipeline(item_id, status="paused", base_dir=base)
    _log(item_id, "pipeline_paused", base)
    return "paused"


def resume(item_id: str, phase: str = "ship", base_dir: str | Path | None = None) -> str:
    base = str(base_dir if base_dir is not None else BASE_DIR)
    cfg = _config().get("pipeline", {})
    if phase != "ship":
        _set_pipeline(item_id, status="running", current_phase=phase, base_dir=base)
        return run(item_id, base)
    data, _ = _read_task(item_id, base)
    if not _gate_approved(data, "ship"):
        _log(item_id, "ship_gate_not_approved", base)
        print(f"[pipeline] Gate de ship não aprovado para {item_id}.", file=sys.stderr)
        return "ship_gate_not_approved"
    result = _run_phase(item_id, "ship", base, cfg)
    if result == "done":
        _set_pipeline(item_id, status="done", current_phase="ship", base_dir=base)
        _log(item_id, "pipeline_done", base)
        return "done"
    return result


def status(item_id: str, base_dir: str | Path | None = None) -> str:
    base = str(base_dir if base_dir is not None else BASE_DIR)
    data, _ = _read_task(item_id, base)
    pipeline = data.get("pipeline", {})
    value = pipeline.get("status", "unknown")
    print(value)
    adapter_used = pipeline.get("adapter_used")
    if adapter_used:
        print(f"adapter_used: {adapter_used}")
    current_task = pipeline.get("current_task")
    if current_task:
        print(f"current_task: {current_task}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-orquestra fases do Agent Harness.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("item")
    status_p = sub.add_parser("status")
    status_p.add_argument("item")
    pause_p = sub.add_parser("pause")
    pause_p.add_argument("item")
    resume_p = sub.add_parser("resume")
    resume_p.add_argument("item")
    resume_p.add_argument("phase", nargs="?", default="ship")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "run":
            run(args.item)
        elif args.cmd == "status":
            status(args.item)
        elif args.cmd == "pause":
            pause(args.item)
        elif args.cmd == "resume":
            resume(args.item, args.phase)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
