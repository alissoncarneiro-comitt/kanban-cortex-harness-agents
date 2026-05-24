#!/usr/bin/env python3
"""
pipeline.py — orquestrador fire-and-forget entre skills do Agent Harness.

FEAT-007 TASK-001.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

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


def _clear_phase_status(item_id: str, phase: str, base_dir: str | Path | None = None) -> None:
    data, path = _read_task(item_id, base_dir)
    data["phase_status"][phase] = None
    data["pipeline"]["last_updated"] = _now_iso()
    _write_yaml(path, data)


def _gate_approved(data: dict, gate: str) -> bool:
    gates = data.get("gates", {})
    if not isinstance(gates, dict):
        return False
    value = gates.get(gate, {})
    return isinstance(value, dict) and value.get("approved") is True


def _invoke_skill(skill_file: str | Path, item: str, base_dir: str | Path = BASE_DIR) -> int:
    """Invoca o Claude CLI com o conteúdo do skill em uma sessão separada."""
    skill_path = Path(base_dir) / skill_file
    if not skill_path.exists():
        skill_path = Path(skill_file)
    if not skill_path.exists():
        raise FileNotFoundError(f"skill file não encontrado: {skill_file}")
    if shutil.which("claude") is None:
        print("claude CLI ausente", file=sys.stderr)
        return 1
    prompt = f"{skill_path.read_text(encoding='utf-8')}\n\nITEM={item}\n"
    completed = subprocess.run(["claude", "-p", prompt], cwd=base_dir, check=False)
    return completed.returncode


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


def _run_phase(item_id: str, phase: str, base_dir: str | Path, cfg: dict) -> str:
    phase_cfg = _phase_config(phase)
    skill_file = phase_cfg["skill_file"]
    _set_pipeline(item_id, status="running", current_phase=phase, base_dir=base_dir)
    _clear_phase_status(item_id, phase, base_dir)
    _log(item_id, f"phase_start {phase}", base_dir)
    try:
        exit_code = _invoke_skill(skill_file, item_id, base_dir)
    except Exception as exc:
        _set_pipeline(item_id, status="error", error=str(exc), base_dir=base_dir)
        _log(item_id, f"phase_error {phase}: {exc}", base_dir)
        return "error"
    if exit_code != 0:
        _set_pipeline(item_id, status="error", error=f"{phase} exit code {exit_code}", base_dir=base_dir)
        _log(item_id, f"phase_exit_nonzero {phase}: {exit_code}", base_dir)
        return "error"
    result = _poll_until_phase_done(
        item_id,
        phase,
        base_dir,
        timeout_minutes=cfg.get("phase_timeout_minutes", 60),
        poll_interval=cfg.get("poll_interval_seconds", 5),
    )
    _log(item_id, f"phase_result {phase}: {result}", base_dir)
    if result == "timeout":
        _set_pipeline(item_id, status="error", error=f"timeout em {phase}", base_dir=base_dir)
        return "error"
    return result


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
        result = _run_phase(item_id, "build", base, cfg)
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
    value = data["pipeline"].get("status", "unknown")
    print(value)
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
