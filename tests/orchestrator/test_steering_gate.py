from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

_spec = importlib.util.spec_from_file_location(
    "steering_gate", SCRIPTS_ROOT / "steering-gate.py"
)
assert _spec and _spec.loader
steering_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(steering_gate)

FIXTURES = Path(__file__).parent / "fixtures"


def _write_board(path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "board_sample.yaml").read_text(encoding="utf-8"))
    data["board"]["items"]["discover"] = [data["board"]["items"]["build"].pop(0)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_run_gate_approve_brief_moves_to_spec(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    _write_board(board_path)

    rc = steering_gate.run_gate("FEAT-013", gate="approve-brief", board_path=board_path)

    assert rc == 0
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert data["board"]["items"]["spec"][0]["id"] == "FEAT-013"


def test_run_gate_approve_tasks_moves_to_build(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = yaml.safe_load((FIXTURES / "board_sample.yaml").read_text(encoding="utf-8"))
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["spec"] = [item]
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    rc = steering_gate.run_gate("FEAT-013", gate="approve-tasks", board_path=board_path)

    assert rc == 0
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert data["board"]["items"]["build"][0]["id"] == "FEAT-013"


def test_run_gate_discover_start_moves_to_discover(tmp_path: Path) -> None:
    board_path = tmp_path / "board.yaml"
    data = yaml.safe_load((FIXTURES / "board_sample.yaml").read_text(encoding="utf-8"))
    item = data["board"]["items"]["build"].pop(0)
    data["board"]["items"]["backlog"].append(item)
    board_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    rc = steering_gate.run_gate("FEAT-013", gate="discover-start", board_path=board_path)

    assert rc == 0
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert any(entry["id"] == "FEAT-013" for entry in data["board"]["items"]["discover"])


def test_run_gate_disabled_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    board_path = tmp_path / "board.yaml"
    _write_board(board_path)
    monkeypatch.setenv("BOARD_AUTO_PROMOTE", "false")

    rc = steering_gate.run_gate("FEAT-013", gate="approve-brief", board_path=board_path)

    assert rc == 0
    data = yaml.safe_load(board_path.read_text(encoding="utf-8"))
    assert data["board"]["items"]["discover"][0]["id"] == "FEAT-013"
