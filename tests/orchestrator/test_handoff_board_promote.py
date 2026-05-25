from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from orchestrator import handoff as handoff_module  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _load_board_fixture() -> dict:
    return yaml.safe_load((FIXTURES / "board_sample.yaml").read_text(encoding="utf-8"))


def _minimal_task_yaml() -> dict:
    return {
        "id": "FEAT-013",
        "pipeline": {
            "status": "idle",
            "current_phase": None,
            "rejection_count": 0,
            "error": "",
            "started_at": None,
            "last_updated": None,
        },
        "phase_status": {
            "build": None,
            "review": None,
            "test": None,
            "ship": None,
        },
        "phase_sessions": {
            "build": None,
            "review": None,
            "test": None,
            "ship": None,
        },
    }


def _setup_kanban(tmp_path: Path) -> tuple[Path, Path]:
    kanban = tmp_path / ".agents" / "kanban"
    item_dir = kanban / "in-progress" / "FEAT-013"
    item_dir.mkdir(parents=True)
    board_path = kanban / "board.yaml"
    board_path.write_text(
        yaml.safe_dump(_load_board_fixture(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    task_path = item_dir / "task.yaml"
    task_path.write_text(
        yaml.safe_dump(_minimal_task_yaml(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return board_path, task_path


def _column_ids(board_path: Path, column: str) -> list[str]:
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    entries = data["board"]["items"].get(column, [])
    return [entry["id"] for entry in entries if isinstance(entry, dict)]


@pytest.fixture(autouse=True)
def _reset_base_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(handoff_module, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("BOARD_AUTO_PROMOTE", raising=False)


def test_handoff_build_done_promotes_board_to_review(tmp_path: Path) -> None:
    board_path, _ = _setup_kanban(tmp_path)

    rc = handoff_module.record_handoff("FEAT-013", "build", "done")

    assert rc == 0
    assert "FEAT-013" in _column_ids(board_path, "review")
    assert "FEAT-013" not in _column_ids(board_path, "build")


def test_handoff_per_task_build_does_not_promote_board(tmp_path: Path) -> None:
    board_path, task_path = _setup_kanban(tmp_path)

    rc = handoff_module.record_handoff(
        "FEAT-013",
        "build",
        "done",
        from_task="TASK-001",
    )

    assert rc == 0
    assert "FEAT-013" in _column_ids(board_path, "build")
    data = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    assert data["task_progress"]["TASK-001"] == "complete"
    assert data["phase_status"]["build"] is None


def test_handoff_review_changes_requested_returns_board_to_build(tmp_path: Path) -> None:
    board_path, _ = _setup_kanban(tmp_path)
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    card = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["review"] = [card]
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    rc = handoff_module.record_handoff("FEAT-013", "review", "changes_requested")

    assert rc == 0
    assert "FEAT-013" in _column_ids(board_path, "build")


def test_board_auto_promote_false_skips_column_move(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    board_path, _ = _setup_kanban(tmp_path)
    monkeypatch.setenv("BOARD_AUTO_PROMOTE", "false")

    rc = handoff_module.record_handoff("FEAT-013", "build", "done")

    assert rc == 0
    assert "FEAT-013" in _column_ids(board_path, "build")


def test_missing_item_on_board_does_not_fail_handoff(tmp_path: Path) -> None:
    kanban = tmp_path / ".agents" / "kanban"
    item_dir = kanban / "in-progress" / "FEAT-013"
    item_dir.mkdir(parents=True)
    board_data = _load_board_fixture()
    board_data["board"]["items"]["build"] = []
    board_path = kanban / "board.yaml"
    board_path.write_text(yaml.safe_dump(board_data, sort_keys=False), encoding="utf-8")
    task_path = item_dir / "task.yaml"
    task_path.write_text(yaml.safe_dump(_minimal_task_yaml(), sort_keys=False), encoding="utf-8")

    rc = handoff_module.record_handoff("FEAT-013", "build", "done")

    assert rc == 0
    data = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    assert data["phase_status"]["build"] == "done"
