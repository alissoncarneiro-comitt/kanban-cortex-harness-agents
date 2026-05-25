"""Project registry loader for cockpit hub navigation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - dependency is expected but we keep fallback explicit
    import yaml
except ImportError as exc:  # pragma: no cover
    yaml = None  # type: ignore[assignment]
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


DEFAULT_REGISTRY_PATH = Path("config") / "project-registry.yaml"
ALLOWED_SOURCE_MODES = {"project", "hub"}


class ProjectRegistryError(ValueError):
    """Raised when the project registry file is malformed."""


@dataclass(frozen=True)
class ProjectEntry:
    project_id: str
    name: str
    root_path: Path
    source_mode: str = "project"
    board_path: Path = Path(".agents") / "kanban" / "board.yaml"
    active: bool = False


@dataclass(frozen=True)
class ProjectRegistry:
    version: str
    projects: list[ProjectEntry]


def add_or_update_project(registry: ProjectRegistry, entry: ProjectEntry) -> ProjectRegistry:
    projects = [project for project in registry.projects if project.project_id != entry.project_id]
    projects.append(entry)
    return ProjectRegistry(version=registry.version, projects=projects)


def save_project_registry(path: Path | str, registry: ProjectRegistry) -> None:
    if yaml is None:  # pragma: no cover - exercised only when dependency missing
        raise ProjectRegistryError("PyYAML is required to save the project registry")

    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": registry.version,
        "projects": [
            {
                "project_id": project.project_id,
                "name": project.name,
                "root_path": str(project.root_path),
                "source_mode": project.source_mode,
                "board_path": str(project.board_path),
                "active": project.active,
            }
            for project in registry.projects
        ],
    }
    registry_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_project_registry(path: Path | str | None = None) -> ProjectRegistry:
    if yaml is None:  # pragma: no cover - exercised only when dependency missing
        raise ProjectRegistryError(
            "PyYAML is required to load the project registry"
        ) from _YAML_IMPORT_ERROR

    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        return ProjectRegistry(version="1.0", projects=[])

    raw = registry_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw) or {}
    except Exception as exc:  # pragma: no cover - delegated to caller contract
        raise ProjectRegistryError(f"invalid project registry YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ProjectRegistryError("project registry must be a mapping")

    version = str(data.get("version", "1.0")).strip() or "1.0"
    raw_projects = data.get("projects", [])
    if raw_projects is None:
        raw_projects = []
    if not isinstance(raw_projects, list):
        raise ProjectRegistryError("projects must be a list")

    projects = [_parse_project_entry(item, index) for index, item in enumerate(raw_projects, start=1)]
    return ProjectRegistry(version=version, projects=projects)


def _parse_project_entry(item: Any, index: int) -> ProjectEntry:
    if not isinstance(item, dict):
        raise ProjectRegistryError(f"project entry #{index} must be a mapping")

    project_id = _require_text(item, "project_id", index)
    name = _require_text(item, "name", index)
    root_path_text = _require_text(item, "root_path", index)
    if not root_path_text.strip():
        raise ProjectRegistryError(f"project entry #{index} root_path cannot be empty")
    root_path = Path(root_path_text).expanduser()
    if not root_path.is_absolute():
        raise ProjectRegistryError(f"project entry #{index} root_path must be absolute")

    source_mode = str(item.get("source_mode", "project")).strip().lower() or "project"
    if source_mode not in ALLOWED_SOURCE_MODES:
        source_mode = "project"

    board_path_text = str(item.get("board_path", Path(".agents") / "kanban" / "board.yaml")).strip()
    board_path = Path(board_path_text or ".agents/kanban/board.yaml")

    return ProjectEntry(
        project_id=project_id,
        name=name,
        root_path=root_path.resolve(strict=False),
        source_mode=source_mode,
        board_path=board_path,
        active=bool(item.get("active", False)),
    )


def _require_text(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if value is None:
        raise ProjectRegistryError(f"project entry #{index} missing required field: {key}")
    text = str(value).strip()
    if not text:
        raise ProjectRegistryError(f"project entry #{index} field {key} cannot be empty")
    return text


def resolve_project_board_path(entry: ProjectEntry) -> Path:
    root_path = entry.root_path.expanduser().resolve(strict=False)
    board_path = entry.board_path.expanduser()
    candidate = board_path if board_path.is_absolute() else root_path / board_path
    resolved_candidate = candidate.resolve(strict=False)

    try:
        resolved_candidate.relative_to(root_path)
    except ValueError as exc:
        raise ProjectRegistryError(
            f"project {entry.project_id} board_path escapes registered root"
        ) from exc

    return resolved_candidate
