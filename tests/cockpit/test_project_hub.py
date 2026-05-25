from __future__ import annotations

import sys
from pathlib import Path
import json
import threading
import urllib.request
from urllib.error import HTTPError

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cockpit.project_registry import (
    ProjectRegistryError,
    ProjectEntry,
    ProjectRegistry,
    add_or_update_project,
    save_project_registry,
    load_project_registry,
)
from scripts.cockpit import server as cockpit_server


def test_load_project_registry_returns_projects(tmp_path: Path) -> None:
    registry_path = tmp_path / "project-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "projects": [
                    {
                        "project_id": "agent-swarm-kanban",
                        "name": "agent-swarm-kanban",
                        "root_path": "/workspace/agent-swarm-kanban",
                        "source_mode": "project",
                        "board_path": ".agents/kanban/board.yaml",
                        "active": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    registry = load_project_registry(registry_path)

    assert registry.version == "1.0"
    assert len(registry.projects) == 1
    project = registry.projects[0]
    assert project.project_id == "agent-swarm-kanban"
    assert project.name == "agent-swarm-kanban"
    assert project.root_path == Path("/workspace/agent-swarm-kanban")
    assert project.source_mode == "project"
    assert project.board_path == Path(".agents/kanban/board.yaml")
    assert project.active is True


def test_load_project_registry_defaults_unknown_source_mode_to_project(tmp_path: Path) -> None:
    registry_path = tmp_path / "project-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "projects": [
                    {
                        "project_id": "alpha",
                        "name": "Alpha",
                        "root_path": "/workspace/alpha",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    registry = load_project_registry(registry_path)

    assert registry.projects[0].source_mode == "project"


def test_load_project_registry_missing_file_returns_empty_registry(tmp_path: Path) -> None:
    registry = load_project_registry(tmp_path / "missing.yaml")

    assert registry.version == "1.0"
    assert registry.projects == []


def test_load_project_registry_rejects_invalid_root_path(tmp_path: Path) -> None:
    registry_path = tmp_path / "project-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "projects": [
                    {
                        "project_id": "alpha",
                        "name": "Alpha",
                        "root_path": "",
                        "source_mode": "project",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProjectRegistryError):
        load_project_registry(registry_path)


def test_load_project_registry_rejects_relative_root_path(tmp_path: Path) -> None:
    registry_path = tmp_path / "project-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "projects": [
                    {
                        "project_id": "alpha",
                        "name": "Alpha",
                        "root_path": "relative/workspace",
                        "source_mode": "project",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProjectRegistryError, match="must be absolute"):
        load_project_registry(registry_path)


def test_add_or_update_project_appends_new_project(tmp_path: Path) -> None:
    registry_path = tmp_path / "project-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"version": "1.0", "projects": []}, sort_keys=False),
        encoding="utf-8",
    )

    registry = load_project_registry(registry_path)
    updated = add_or_update_project(
        registry,
        ProjectEntry(
            project_id="alpha",
            name="Alpha",
            root_path=Path("/workspace/alpha"),
            source_mode="project",
            board_path=Path(".agents/kanban/board.yaml"),
            active=True,
        ),
    )

    assert len(updated.projects) == 1
    assert updated.projects[0].project_id == "alpha"
    assert updated.projects[0].active is True


def test_add_or_update_project_replaces_existing_project_by_id() -> None:
    registry = ProjectRegistry(
        version="1.0",
        projects=[
            ProjectEntry(
                project_id="alpha",
                name="Alpha",
                root_path=Path("/workspace/alpha-old"),
                source_mode="project",
                board_path=Path(".agents/kanban/board.yaml"),
                active=False,
            )
        ],
    )

    updated = add_or_update_project(
        registry,
        ProjectEntry(
            project_id="alpha",
            name="Alpha Updated",
            root_path=Path("/workspace/alpha-new"),
            source_mode="hub",
            board_path=Path("hub/board.yaml"),
            active=True,
        ),
    )

    assert len(updated.projects) == 1
    assert updated.projects[0].name == "Alpha Updated"
    assert updated.projects[0].root_path == Path("/workspace/alpha-new")
    assert updated.projects[0].source_mode == "hub"
    assert updated.projects[0].active is True


def test_build_cockpit_config_defaults_project_hub_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COCKPIT_PROJECT_HUB_ENABLED", raising=False)

    assert cockpit_server.build_cockpit_config()["project_hub_enabled"] is False


def test_cockpit_projects_endpoint_and_contextual_board_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "alpha"
    kanban_root = project_root / ".agents" / "kanban"
    item_dir = kanban_root / "backlog" / "FEAT-900"
    item_dir.mkdir(parents=True)
    (kanban_root).mkdir(parents=True, exist_ok=True)
    (kanban_root / "board.yaml").write_text(
        yaml.safe_dump(
            {
                "board": {
                    "items": {
                        "backlog": [
                            {
                                "id": "FEAT-900",
                                "title": "Hub test",
                                "class_of_service": "standard",
                            }
                        ],
                        "discover": [],
                        "spec": [],
                        "build": [],
                        "review": [],
                        "test": [],
                        "ship": [],
                        "done": [],
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (item_dir / "brief.md").write_text("# Brief\n", encoding="utf-8")

    registry_path = tmp_path / "AGENT_HOME" / "config" / "project-registry.yaml"
    save_project_registry(
        registry_path,
        ProjectRegistry(
            version="1.0",
            projects=[
                ProjectEntry(
                    project_id="alpha",
                    name="Alpha",
                    root_path=project_root,
                    source_mode="project",
                    board_path=Path(".agents/kanban/board.yaml"),
                    active=True,
                )
            ],
        ),
    )

    monkeypatch.setenv("COCKPIT_PROJECT_HUB_ENABLED", "true")
    monkeypatch.setattr(cockpit_server, "PROJECT_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(cockpit_server, "AGENT_HOME", registry_path.parents[1])

    server = cockpit_server.make_server(
        host="127.0.0.1",
        port=0,
        board_path=kanban_root / "board.yaml",
        html_path=Path(__file__).resolve().parent.parent / "src" / "cockpit" / "board.html",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        projects = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/projects").read().decode("utf-8")
        )
        assert projects["enabled"] is True
        assert len(projects["projects"]) == 1
        assert projects["projects"][0]["project_id"] == "alpha"

        board = json.loads(
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/board?project_id=alpha&source=project"
            ).read().decode("utf-8")
        )
        assert board["board"]["items"]["backlog"][0]["id"] == "FEAT-900"

        item = json.loads(
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/item/FEAT-900?project_id=alpha&source=project"
            ).read().decode("utf-8")
        )
        assert item["item"]["id"] == "FEAT-900"
        assert item["artifact_path"] == str(item_dir)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_cockpit_rejects_unknown_project_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "alpha"
    kanban_root = project_root / ".agents" / "kanban"
    kanban_root.mkdir(parents=True)
    (kanban_root / "board.yaml").write_text(
        yaml.safe_dump(
            {"board": {"items": {"backlog": [], "discover": [], "spec": [], "build": [], "review": [], "test": [], "ship": [], "done": []}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    registry_path = tmp_path / "AGENT_HOME" / "config" / "project-registry.yaml"
    save_project_registry(
        registry_path,
        ProjectRegistry(
            version="1.0",
            projects=[
                ProjectEntry(
                    project_id="alpha",
                    name="Alpha",
                    root_path=project_root,
                    source_mode="project",
                    board_path=Path(".agents/kanban/board.yaml"),
                    active=True,
                )
            ],
        ),
    )

    monkeypatch.setenv("COCKPIT_PROJECT_HUB_ENABLED", "true")
    monkeypatch.setattr(cockpit_server, "PROJECT_REGISTRY_PATH", registry_path)

    server = cockpit_server.make_server(
        host="127.0.0.1",
        port=0,
        board_path=kanban_root / "board.yaml",
        html_path=Path(__file__).resolve().parent.parent / "src" / "cockpit" / "board.html",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        with pytest.raises(HTTPError) as exc:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/board?project_id=missing&source=project"
            )
        assert exc.value.code == 404
        payload = json.loads(exc.value.read().decode("utf-8"))
        assert "project not registered" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_cockpit_rejects_path_traversal_item_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "alpha"
    kanban_root = project_root / ".agents" / "kanban"
    kanban_root.mkdir(parents=True)
    (kanban_root / "board.yaml").write_text(
        yaml.safe_dump(
            {"board": {"items": {"backlog": [], "discover": [], "spec": [], "build": [], "review": [], "test": [], "ship": [], "done": []}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    registry_path = tmp_path / "AGENT_HOME" / "config" / "project-registry.yaml"
    save_project_registry(
        registry_path,
        ProjectRegistry(
            version="1.0",
            projects=[
                ProjectEntry(
                    project_id="alpha",
                    name="Alpha",
                    root_path=project_root,
                    source_mode="project",
                    board_path=Path(".agents/kanban/board.yaml"),
                    active=True,
                )
            ],
        ),
    )

    monkeypatch.setenv("COCKPIT_PROJECT_HUB_ENABLED", "true")
    monkeypatch.setattr(cockpit_server, "PROJECT_REGISTRY_PATH", registry_path)

    server = cockpit_server.make_server(
        host="127.0.0.1",
        port=0,
        board_path=kanban_root / "board.yaml",
        html_path=Path(__file__).resolve().parent.parent / "src" / "cockpit" / "board.html",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        with pytest.raises(HTTPError) as exc:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/item/../secrets?project_id=alpha&source=project"
            )
        assert exc.value.code == 400
        payload = json.loads(exc.value.read().decode("utf-8"))
        assert payload["error"] == "invalid item id"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_cockpit_rejects_escaped_board_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "alpha"
    kanban_root = project_root / ".agents" / "kanban"
    kanban_root.mkdir(parents=True)
    (kanban_root / "board.yaml").write_text(
        yaml.safe_dump(
            {"board": {"items": {"backlog": [], "discover": [], "spec": [], "build": [], "review": [], "test": [], "ship": [], "done": []}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    registry_path = tmp_path / "AGENT_HOME" / "config" / "project-registry.yaml"
    save_project_registry(
        registry_path,
        ProjectRegistry(
            version="1.0",
            projects=[
                ProjectEntry(
                    project_id="alpha",
                    name="Alpha",
                    root_path=project_root,
                    source_mode="project",
                    board_path=Path("../outside.yaml"),
                    active=True,
                )
            ],
        ),
    )

    monkeypatch.setenv("COCKPIT_PROJECT_HUB_ENABLED", "true")
    monkeypatch.setattr(cockpit_server, "PROJECT_REGISTRY_PATH", registry_path)

    server = cockpit_server.make_server(
        host="127.0.0.1",
        port=0,
        board_path=kanban_root / "board.yaml",
        html_path=Path(__file__).resolve().parent.parent / "src" / "cockpit" / "board.html",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        with pytest.raises(HTTPError) as exc:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/board?project_id=alpha&source=project"
            )
        assert exc.value.code == 400
        payload = json.loads(exc.value.read().decode("utf-8"))
        assert "escapes registered root" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
