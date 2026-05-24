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

def record_handoff(item_id: str, phase: str, status: str) -> int:
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

    # Garante seções necessárias
    _ensure_pipeline_section(data)

    # Atualiza phase_status
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

    print(f"[handoff] {item_id} phase={phase} status={status} registrado.", file=sys.stdout)

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
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return record_handoff(args.item, args.phase, args.status)


if __name__ == "__main__":
    sys.exit(main())
