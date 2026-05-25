from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

_spec = importlib.util.spec_from_file_location(
    "board_validate", SCRIPTS_ROOT / "board-validate.py"
)
assert _spec and _spec.loader
board_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board_validate)

FIXTURES = Path(__file__).parent / "fixtures" / "board_validate"


def _load_fixture(name: str) -> dict:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def test_expected_min_column_build_done() -> None:
    phase_status = {"build": "done", "review": None, "test": None, "ship": None}
    assert board_validate.expected_min_column_from_phase_status(phase_status) == "review"


def test_expected_min_column_review_approved() -> None:
    phase_status = {"build": "done", "review": "approved", "test": None, "ship": None}
    assert board_validate.expected_min_column_from_phase_status(phase_status) == "test"


def test_check_phase_column_drift_warns_when_behind(tmp_path: Path) -> None:
    board = _load_fixture("board_drifted.yaml")
    board_path = tmp_path / "board.yaml"
    board_path.write_text(yaml.safe_dump(board, sort_keys=False), encoding="utf-8")

    in_progress = tmp_path / "in-progress"
    item_dir = in_progress / "FEAT-013"
    item_dir.mkdir(parents=True)
    (item_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-013",
                "phase_status": {
                    "build": "done",
                    "review": None,
                    "test": None,
                    "ship": None,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = board_validate.load_board(board_path)
    warnings = board_validate.check_phase_column_drift(loaded, in_progress)

    assert len(warnings) == 1
    assert "FEAT-013" in warnings[0]
    assert "build" in warnings[0]
    assert "review" in warnings[0]


def test_check_phase_column_drift_ok_when_aligned(tmp_path: Path) -> None:
    board = _load_fixture("board_drifted.yaml")
    board["board"]["items"]["build"] = []
    board["board"]["items"]["review"] = [{"id": "FEAT-013", "title": "Drift test"}]
    board_path = tmp_path / "board.yaml"
    board_path.write_text(yaml.safe_dump(board, sort_keys=False), encoding="utf-8")

    in_progress = tmp_path / "in-progress"
    item_dir = in_progress / "FEAT-013"
    item_dir.mkdir(parents=True)
    (item_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-013",
                "phase_status": {"build": "done"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = board_validate.load_board(board_path)
    warnings = board_validate.check_phase_column_drift(loaded, in_progress)

    assert warnings == []
