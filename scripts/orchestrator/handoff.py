#!/usr/bin/env python3
"""
handoff.py — Phase Completion Writer para o Pipeline de Auto-Orquestração.

FEAT-007 TASK-002.

Chamado ao fim de cada skill para registrar a conclusão em task.yaml.
Nunca falha silenciosamente — sempre retorna exit code útil.

Uso:
    python scripts/orchestrator/handoff.py --item FEAT-XXX --phase build --status done
    python scripts/orchestrator/handoff.py --item FEAT-XXX --phase review --status approved
    python scripts/orchestrator/handoff.py --item FEAT-XXX --phase review --status changes_requested
    python scripts/orchestrator/handoff.py --item FEAT-XXX --phase test --status passed
    python scripts/orchestrator/handoff.py --item FEAT-XXX --phase ship --status done
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# Feature flag: PIPELINE_ENABLED. Recomendado mas não obrigatório.
import os as _os

# ---------------------------------------------------------------------------
# Constantes de validação
# ---------------------------------------------------------------------------

VALID_PHASES = frozenset({"build", "review", "test", "ship"})

VALID_STATUSES = frozenset({
    "done",
    "approved",
    "changes_requested",
    "rejected",
    "passed",
    "failed",
})

# Mapeamento de fases para os status permitidos
PHASE_ALLOWED_STATUSES: dict[str, frozenset[str]] = {
    "build": frozenset({"done", "failed"}),
    "review": frozenset({"approved", "changes_requested", "rejected"}),
    "test": frozenset({"passed", "failed"}),
    "ship": frozenset({"done", "failed"}),
}

# ---------------------------------------------------------------------------
# Configuração de caminhos (patcheável nos testes)
# ---------------------------------------------------------------------------

BASE_DIR: str = "."  # Raiz do projeto; sobrescrito nos testes


def _task_yaml_path(item_id: str) -> Path:
    root = Path(BASE_DIR)
    candidates = [
        root / "in-progress" / item_id / "task.yaml",
        root / ".agents" / "kanban" / "in-progress" / item_id / "task.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


# ---------------------------------------------------------------------------
# Funções internas
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_task_yaml(item_id: str) -> tuple[dict, Path]:
    path = _task_yaml_path(item_id)
    if not path.exists():
        raise FileNotFoundError(f"task.yaml não encontrado: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"task.yaml inválido (não é um dict): {path}")
    return data, path


def _write_task_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _call_audit_writer(item_id: str, phase: str, status: str) -> None:
    """Emite evento para audit_writer.py se disponível. Nunca bloqueia."""
    audit_cmd = [
        sys.executable,
        "scripts/audit_writer.py",
        "phase_end",
        "--item", item_id,
        "--phase", phase,
        "--status", status,
    ]
    try:
        subprocess.run(audit_cmd, check=False, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # audit_writer ausente ou timeout → prosseguir sem interromper
        pass


_PHASES = ("build", "review", "test", "ship")

# Allowlist padrão por fase destino (FEAT-011 TASK-005 / AC-3)
DEFAULT_ARTIFACTS_ALLOWED: dict[str, list[str]] = {
    "build": [
        "design.md",
        "tasks.md",
        ".agents/steering/conventions.md",
    ],
    "review": [
        "design.md",
        "tasks.md",
        "src/",
    ],
    "test": [
        "requirements.md",
        "src/",
    ],
    "ship": [
        "qa-report.md",
        "task.yaml",
    ],
}

FORBIDDEN_ARTIFACTS_BY_PHASE: dict[str, frozenset[str]] = {
    "review": frozenset({
        "review-report.md",
        "requirements.md",
        "brief.md",
        ".env",
        "Implementation Notes",
    }),
    "test": frozenset({
        "review-report.md",
    }),
    "build": frozenset({
        "review-report.md",
        "review-feedback.md",
    }),
    "ship": frozenset(),
}


def _snapshot_phase_sessions(data: dict) -> dict[str, object]:
    """Captura phase_sessions existentes antes de mutar task.yaml (FEAT-011 TASK-003)."""
    existing = data.get("phase_sessions")
    if not isinstance(existing, dict):
        return {}
    return {phase: existing.get(phase) for phase in _PHASES if phase in existing}


def _ensure_phase_sessions(
    data: dict,
    preserved: dict[str, object] | None = None,
) -> None:
    """Garante schema phase_sessions sem apagar UUIDs já gravados pelo pipeline."""
    if "phase_sessions" not in data or not isinstance(data["phase_sessions"], dict):
        data["phase_sessions"] = {}
    sessions = data["phase_sessions"]
    for phase in _PHASES:
        sessions.setdefault(phase, None)
    if preserved:
        for phase, value in preserved.items():
            if phase in _PHASES and value is not None:
                sessions[phase] = value


def _handoff_packet_path(task_yaml_path: Path) -> Path:
    return task_yaml_path.parent / "handoff-packet.yaml"


def _resolve_next_phase(phase: str, status: str) -> Optional[str]:
    """Próxima fase do pipeline após conclusão da fase atual."""
    if status in ("failed", "rejected"):
        return None
    if phase == "build" and status == "done":
        return "review"
    if phase == "review" and status == "approved":
        return "test"
    if phase == "review" and status == "changes_requested":
        return "build"
    if phase == "test" and status == "passed":
        return "ship"
    return None


def validate_artifacts_allowed(
    to_phase: Optional[str],
    artifacts_allowed: list[str],
) -> list[str]:
    """Retorna entradas proibidas para to_phase (AC-3)."""
    if not to_phase:
        return []
    forbidden = FORBIDDEN_ARTIFACTS_BY_PHASE.get(to_phase, frozenset())
    violations: list[str] = []
    for entry in artifacts_allowed:
        normalized = entry.strip()
        for bad in forbidden:
            if normalized == bad or bad in normalized:
                violations.append(normalized)
                break
    return violations


def _git_snapshot() -> dict[str, Optional[str]]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return {"branch": branch or None, "commit": commit or None}
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {"branch": None, "commit": None}


def write_handoff_packet(
    item_id: str,
    task_yaml_path: Path,
    *,
    phase: str,
    status: str,
    task_yaml_data: dict,
    from_task: Optional[str] = None,
    artifacts_allowed: Optional[list[str]] = None,
) -> None:
    """Escreve handoff-packet.yaml para a transição de fase (FEAT-011 TASK-005)."""
    to_phase = _resolve_next_phase(phase, status)
    if artifacts_allowed is None:
        if to_phase and to_phase in DEFAULT_ARTIFACTS_ALLOWED:
            artifacts_allowed = list(DEFAULT_ARTIFACTS_ALLOWED[to_phase])
        else:
            artifacts_allowed = []

    violations = validate_artifacts_allowed(to_phase, artifacts_allowed)
    for entry in violations:
        print(
            f"AVISO [handoff-packet]: artefato '{entry}' proibido para fase destino "
            f"'{to_phase}' — remova de artifacts_allowed (AC-3).",
            file=sys.stderr,
        )

    sessions = task_yaml_data.get("phase_sessions") or {}
    session_id = sessions.get(phase) if isinstance(sessions, dict) else None

    existing_retry = False
    packet_path = _handoff_packet_path(task_yaml_path)
    if packet_path.exists():
        try:
            with open(packet_path) as f:
                prev = yaml.safe_load(f) or {}
            existing_retry = bool(prev.get("pipeline_retry", False))
        except (OSError, yaml.YAMLError):
            existing_retry = False

    blockers: list[str] = []
    if status in ("failed", "rejected"):
        blockers.append(f"{phase}:{status}")

    packet = {
        "item": item_id,
        "from_phase": phase,
        "to_phase": to_phase,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "git": _git_snapshot(),
        "artifacts_allowed": artifacts_allowed,
        "status": status,
        "blockers": blockers,
        "pipeline_retry": existing_retry,
    }
    if from_task:
        packet["from_task"] = from_task

    with open(packet_path, "w") as f:
        yaml.dump(packet, f, default_flow_style=False, allow_unicode=True)


def _board_auto_promote_enabled() -> bool:
    """BOARD_AUTO_PROMOTE=false desliga sync de coluna (FEAT-013 TASK-002)."""
    value = _os.environ.get("BOARD_AUTO_PROMOTE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _resolve_board_path(task_yaml_path: Path) -> Path:
    """Deriva board.yaml a partir do caminho de task.yaml."""
    parts = task_yaml_path.parts
    if "kanban" in parts:
        idx = parts.index("kanban")
        kanban_root = Path(*parts[: idx + 1])
        return kanban_root / "board.yaml"
    root = Path(BASE_DIR)
    for candidate in (
        root / ".agents" / "kanban" / "board.yaml",
        root / "kanban" / "board.yaml",
    ):
        if candidate.is_file():
            return candidate
    return root / ".agents" / "kanban" / "board.yaml"


def _sync_board_after_handoff(
    item_id: str,
    phase: str,
    status: str,
    task_yaml_path: Path,
    *,
    skip_promote: bool = False,
) -> None:
    """Best-effort: promove coluna no board após handoff (não reverte task.yaml)."""
    if skip_promote or not _board_auto_promote_enabled():
        return

    try:
        from orchestrator.board_promote import promote, trigger_from_handoff
    except ImportError:  # pragma: no cover
        from board_promote import promote, trigger_from_handoff

    board_path = _resolve_board_path(task_yaml_path)
    trigger = trigger_from_handoff(phase, status)
    try:
        result = promote(item_id, trigger, board_path=board_path)
    except ValueError as exc:
        print(f"WARN [board-promote]: {exc}", file=sys.stderr)
        return
    except (FileNotFoundError, OSError) as exc:
        print(f"WARN [board-promote]: falha ao sincronizar board: {exc}", file=sys.stderr)
        return

    if not result.ok:
        print(
            f"WARN [board-promote]: item={item_id} trigger={trigger} reason={result.reason}",
            file=sys.stderr,
        )
        return
    if result.skipped:
        return
    print(
        f"[board-promote] {item_id} {result.from_column} -> {result.to_column}",
        file=sys.stdout,
    )


def _ensure_pipeline_section(data: dict) -> None:
    """Garante que as seções pipeline e phase_status existem no data."""
    if "pipeline" not in data or not isinstance(data["pipeline"], dict):
        data["pipeline"] = {
            "status": "idle",
            "current_phase": None,
            "rejection_count": 0,
            "error": "",
            "started_at": None,
            "last_updated": None,
        }
    if "phase_status" not in data or not isinstance(data["phase_status"], dict):
        data["phase_status"] = {
            "build": None,
            "review": None,
            "test": None,
            "ship": None,
        }


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def record_handoff(
    item_id: str,
    phase: str,
    status: str,
    *,
    from_task: Optional[str] = None,
    artifacts_allowed: Optional[list[str]] = None,
) -> int:
    """
    Registra a conclusão de uma fase em task.yaml.

    Returns:
        0 em sucesso, 1 em erro de validação ou I/O.
    """
    # Validação de fase
    if phase not in VALID_PHASES:
        print(
            f"ERRO: fase inválida '{phase}'. Permitidas: {sorted(VALID_PHASES)}",
            file=sys.stderr,
        )
        return 1

    # Validação de status
    if status not in VALID_STATUSES:
        print(
            f"ERRO: status inválido '{status}'. Permitidos: {sorted(VALID_STATUSES)}",
            file=sys.stderr,
        )
        return 1

    # Validação de status por fase
    allowed = PHASE_ALLOWED_STATUSES.get(phase, frozenset())
    if status not in allowed:
        print(
            f"ERRO: status '{status}' não é válido para fase '{phase}'. "
            f"Permitidos: {sorted(allowed)}",
            file=sys.stderr,
        )
        return 1

    # Leitura de task.yaml
    try:
        data, path = _read_task_yaml(item_id)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    # Garante seções necessárias (preserva phase_sessions do pipeline — isolamento por fase)
    preserved_sessions = _snapshot_phase_sessions(data)
    _ensure_pipeline_section(data)
    _ensure_phase_sessions(data, preserved_sessions)

    # Per-task progress (FEAT-011 TASK-008): handoff --task atualiza task_progress
    defer_phase_status = False
    if from_task:
        if "task_progress" not in data or not isinstance(data["task_progress"], dict):
            data["task_progress"] = {}
        task_state = status
        if status in ("approved", "passed", "done"):
            task_state = "complete"
        elif status in ("rejected", "changes_requested"):
            task_state = "failed"
        data["task_progress"][from_task] = task_state
        if phase == "build" and status == "done":
            defer_phase_status = True

    if not defer_phase_status:
        data["phase_status"][phase] = status

    # Tratamento especial: changes_requested incrementa rejection_count
    if phase == "review" and status == "changes_requested":
        data["pipeline"]["rejection_count"] = data["pipeline"].get("rejection_count", 0) + 1

    # Atualiza timestamp
    data["pipeline"]["last_updated"] = _now_iso()

    # Persiste
    try:
        _write_task_yaml(path, data)
    except OSError as exc:
        print(f"ERRO ao escrever task.yaml: {exc}", file=sys.stderr)
        return 1

    try:
        write_handoff_packet(
            item_id,
            path,
            phase=phase,
            status=status,
            task_yaml_data=data,
            from_task=from_task,
            artifacts_allowed=artifacts_allowed,
        )
    except OSError as exc:
        print(f"ERRO ao escrever handoff-packet.yaml: {exc}", file=sys.stderr)
        return 1

    print(f"[handoff] {item_id} phase={phase} status={status} registrado.", file=sys.stdout)

    _sync_board_after_handoff(
        item_id,
        phase,
        status,
        path,
        skip_promote=defer_phase_status,
    )

    # Emite evento de auditoria (não-bloqueante)
    _call_audit_writer(item_id, phase, status)

    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Registra conclusão de fase no pipeline de auto-orquestração."
    )
    parser.add_argument("--item", required=True, help="ID do item (ex: FEAT-007)")
    parser.add_argument(
        "--phase",
        required=True,
        choices=sorted(VALID_PHASES),
        help="Fase concluída",
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="Status da conclusão",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Task Kanban de origem (ex: TASK-003) para from_task no handoff-packet",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return record_handoff(
        args.item,
        args.phase,
        args.status,
        from_task=args.task,
    )


if __name__ == "__main__":
    sys.exit(main())
