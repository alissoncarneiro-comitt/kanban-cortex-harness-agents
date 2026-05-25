from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from orchestrator import board_promote as board_promote_module  # noqa: E402
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


def _column_of(board_path: Path, item_id: str) -> str | None:
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    for column, entries in data["board"]["items"].items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") == item_id:
                return column
    return None


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(handoff_module, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("BOARD_AUTO_PROMOTE", raising=False)


def test_e2e_happy_path_build_to_done(tmp_path: Path) -> None:
    board_path, _ = _setup_kanban(tmp_path)
    assert _column_of(board_path, "FEAT-013") == "build"

    sequence = [
        ("build", "done", "review"),
        ("review", "approved", "test"),
        ("test", "passed", "ship"),
        ("ship", "done", "done"),
    ]
    for phase, status, expected_column in sequence:
        rc = handoff_module.record_handoff("FEAT-013", phase, status)
        assert rc == 0
        assert _column_of(board_path, "FEAT-013") == expected_column


def test_e2e_review_fail_loop_then_test(tmp_path: Path) -> None:
    board_path, _ = _setup_kanban(tmp_path)

    assert handoff_module.record_handoff("FEAT-013", "build", "done") == 0
    assert _column_of(board_path, "FEAT-013") == "review"

    assert (
        handoff_module.record_handoff("FEAT-013", "review", "changes_requested") == 0
    )
    assert _column_of(board_path, "FEAT-013") == "build"

    assert handoff_module.record_handoff("FEAT-013", "build", "done") == 0
    assert _column_of(board_path, "FEAT-013") == "review"

    assert handoff_module.record_handoff("FEAT-013", "review", "approved") == 0
    assert _column_of(board_path, "FEAT-013") == "test"


def test_board_promote_cli_promoted(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_path = tmp_path / "board.yaml"
    board_path.write_text(
        yaml.safe_dump(_load_board_fixture(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "board_promote.py",
            "--item",
            "FEAT-013",
            "--trigger",
            "handoff.build.done",
            "--board",
            str(board_path),
        ],
    )

    rc = board_promote_module.main()

    assert rc == 0
    assert "promoted:" in capsys.readouterr().out
    assert _column_of(board_path, "FEAT-013") == "review"


def test_board_promote_cli_unknown_trigger(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_path = tmp_path / "board.yaml"
    board_path.write_text(
        yaml.safe_dump(_load_board_fixture(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "board_promote.py",
            "--item",
            "FEAT-013",
            "--trigger",
            "not.mapped",
            "--board",
            str(board_path),
        ],
    )

    rc = board_promote_module.main()

    assert rc == 0
    assert "noop: unknown trigger" in capsys.readouterr().out


def test_board_promote_cli_duplicate_item_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_board_fixture()
    duplicate = dict(data["board"]["items"]["build"][0])
    data["board"]["items"]["review"] = [duplicate]
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "board_promote.py",
            "--item",
            "FEAT-013",
            "--trigger",
            "handoff.build.done",
            "--board",
            str(board_path),
        ],
    )

    rc = board_promote_module.main()

    assert rc == 1
    assert "DUPLICATE_ITEM_ID" in capsys.readouterr().err


def test_promote_wip_exceeded_still_moves(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_board_fixture()
    data["board"]["items"]["review"] = [
        {"id": f"FEAT-{idx:03d}", "title": f"Fill {idx}"} for idx in range(4)
    ]
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = board_promote_module.promote(
        "FEAT-013",
        "handoff.build.done",
        board_path=board_path,
    )

    assert result.ok is True
    assert result.to_column == "review"
    assert "WIP_EXCEEDED" in capsys.readouterr().err


def test_load_board_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        board_promote_module.load_board(Path("/nonexistent/board.yaml"))


def test_load_board_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "board.yaml"
    bad.write_text("board: [invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML_CORRUPT"):
        board_promote_module.load_board(bad)


def test_promote_dest_column_not_list_coerced(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_board_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["review"] = [item]
    data["board"]["items"]["test"] = "not-a-list"
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = board_promote_module.promote(
        "FEAT-013",
        "handoff.review.approved",
        board_path=board_path,
    )

    assert result.ok is True
    assert result.to_column == "test"
    loaded = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert isinstance(loaded["board"]["items"]["test"], list)
    assert loaded["board"]["items"]["test"][0]["id"] == "FEAT-013"
