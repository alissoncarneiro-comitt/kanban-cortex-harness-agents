"""Resolve and construct phase invocation adapters (FEAT-011 TASK-001)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from orchestrator.adapters import ClaudeAdapter, CursorAdapter, PhaseAdapter

DEFAULT_CONFIG_PATH = Path(".agents/config/pipeline.yaml")


class AdapterNotFoundError(RuntimeError):
    """No adapter could be resolved for the current environment."""


def _load_pipeline_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return {}
    import yaml

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return {}
    pipeline = data.get("pipeline")
    return pipeline if isinstance(pipeline, dict) else {}


def _pick_auto() -> PhaseAdapter | None:
    if shutil.which("agent") is not None:
        return CursorAdapter()
    if shutil.which("claude") is not None:
        return ClaudeAdapter()
    return None


def resolve_adapter(
    pipeline_config: dict[str, Any] | None = None,
    *,
    config_path: Path | None = None,
) -> PhaseAdapter:
    """
    Return adapter for pipeline.invoker: auto | claude | cursor.

    Raises AdapterNotFoundError when the requested adapter is unavailable.
    """
    cfg = pipeline_config if pipeline_config is not None else _load_pipeline_config(config_path)
    invoker = str(cfg.get("invoker", "auto")).strip().lower()

    if invoker == "claude":
        if shutil.which("claude") is None:
            raise AdapterNotFoundError(
                "pipeline.invoker=claude mas claude CLI não está no PATH."
            )
        return ClaudeAdapter()

    if invoker == "cursor":
        if shutil.which("agent") is None:
            raise AdapterNotFoundError(
                "pipeline.invoker=cursor mas agent CLI não está no PATH."
            )
        return CursorAdapter()

    if invoker == "auto":
        adapter = _pick_auto()
        if adapter is None:
            raise AdapterNotFoundError(
                "Nenhum adapter disponível (auto). Instale claude ou Cursor agent CLI."
            )
        return adapter

    raise AdapterNotFoundError(f"pipeline.invoker inválido: {invoker!r}")


def invoke_skill(
    skill_file: str | Path,
    item_id: str,
    base_dir: str | Path = ".",
    *,
    task_id: str | None = None,
    pipeline_config: dict[str, Any] | None = None,
    cwd: str | Path | None = None,
) -> int:
    """Invoke skill via resolved adapter; return exit code 1 if adapter missing."""
    try:
        adapter = resolve_adapter(pipeline_config)
    except AdapterNotFoundError as exc:
        import sys

        print(str(exc), file=sys.stderr)
        return 1
    root = Path(base_dir)
    run_cwd = Path(cwd) if cwd is not None else root
    return adapter.invoke(Path(skill_file), item_id, base_dir=root, task_id=task_id, cwd=run_cwd)
