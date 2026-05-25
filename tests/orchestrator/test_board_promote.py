from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from orchestrator.board_promote import (  # noqa: E402
    PromoteResult,
    find_item_columns,
    promote,
    trigger_from_handoff,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str = "board_sample.yaml") -> dict:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _write_board(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_trigger_from_handoff_build_done() -> None:
    assert trigger_from_handoff("build", "done") == "handoff.build.done"


def test_promote_build_done_moves_to_review(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    _write_board(board_path, _load_fixture())

    result = promote("FEAT-013", "handoff.build.done", board_path=board_path)

    assert result.ok is True
    assert result.from_column == "build"
    assert result.to_column == "review"
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    review_ids = [item["id"] for item in data["board"]["items"]["review"]]
    assert "FEAT-013" in review_ids
    assert "FEAT-013" not in [i["id"] for i in data["board"]["items"]["build"]]


def test_promote_review_approved_moves_to_test(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["review"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "handoff.review.approved", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "test"
    loaded = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert loaded["board"]["items"]["test"][0]["id"] == "FEAT-013"


def test_promote_review_changes_requested_returns_to_build(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["review"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "handoff.review.changes_requested", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "build"
    loaded = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert loaded["board"]["items"]["build"][0]["id"] == "FEAT-013"


def test_promote_test_failed_returns_to_build(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["test"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "handoff.test.failed", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "build"


def test_promote_test_passed_moves_to_ship(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["test"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "handoff.test.passed", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "ship"


def test_promote_ship_done_moves_to_done(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["ship"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "handoff.ship.done", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "done"


def test_promote_steering_approve_brief_moves_to_spec(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    data["board"]["items"]["discover"] = [data["board"]["items"]["build"].pop(0)]
    _write_board(board_path, data)

    result = promote("FEAT-013", "steering.approve.brief", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "spec"


def test_promote_steering_approve_tasks_moves_to_build(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["spec"] = [item]
    _write_board(board_path, data)

    result = promote("FEAT-013", "steering.approve.tasks", board_path=board_path)

    assert result.ok is True
    assert result.to_column == "build"


def test_promote_idempotent_when_already_in_target_column(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    _write_board(board_path, data)

    first = promote("FEAT-013", "handoff.build.done", board_path=board_path)
    second = promote("FEAT-013", "handoff.build.done", board_path=board_path)

    assert first.ok is True
    assert second.ok is True
    assert second.skipped is True
    loaded = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert len(loaded["board"]["items"]["review"]) == 1


def test_promote_missing_item_warns_and_skips(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    _write_board(board_path, _load_fixture())

    result = promote("FEAT-999", "handoff.build.done", board_path=board_path)

    assert result.ok is False
    assert result.reason == "ITEM_NOT_ON_BOARD"


def test_promote_duplicate_item_id_raises(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = _load_fixture()
    duplicate = copy.deepcopy(data["board"]["items"]["build"][0])
    data["board"]["items"]["review"] = [duplicate]
    _write_board(board_path, data)

    with pytest.raises(ValueError, match="DUPLICATE_ITEM_ID"):
        promote("FEAT-013", "handoff.build.done", board_path=board_path)


def test_find_item_columns_single_match() -> None:
    data = _load_fixture()
    matches = find_item_columns(data, "FEAT-013")
    assert matches == [("build", 0)]


def test_unknown_trigger_is_noop(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    _write_board(board_path, _load_fixture())
    before = board_path.read_text(encoding="utf-8")

    result = promote("FEAT-013", "unknown.trigger", board_path=board_path)

    assert result.ok is True
    assert result.skipped is True
    assert board_path.read_text(encoding="utf-8") == before
