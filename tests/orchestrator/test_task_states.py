from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from orchestrator import pipeline, handoff

@pytest.fixture
def mock_task_yaml(tmp_path: Path):
    item_id = "FEAT-015"
    task_dir = tmp_path / ".agents" / "kanban" / "in-progress" / item_id
    task_dir.mkdir(parents=True)
    task_path = task_dir / "task.yaml"
    
    data = {
        "id": item_id,
        "title": "Test Task",
        "gates": {"tasks": {"approved": True}},
        "pipeline": {"status": "idle"},
        "task_progress": {}
    }
    task_path.write_text(yaml.dump(data), encoding="utf-8")
    return item_id, task_path, tmp_path

def test_init_task_progress_sets_pending(mock_task_yaml):
    item_id, task_path, base_dir = mock_task_yaml
    graph = {"TASK-001": [], "TASK-002": ["TASK-001"]}
    
    pipeline._init_task_progress(item_id, graph, base_dir=base_dir)
    
    with task_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    assert data["task_progress"]["TASK-001"] == "pending"
    assert data["task_progress"]["TASK-002"] == "pending"

def test_update_task_status_sets_in_progress(mock_task_yaml):
    item_id, task_path, base_dir = mock_task_yaml
    task_id = "TASK-001"
    
    pipeline._update_task_status(item_id, task_id, "in_progress", base_dir=base_dir)
    
    with task_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # pipeline._update_task_status normaliza "in_progress" → "running" no YAML
    assert data["task_progress"][task_id] == "running"

def test_handoff_maps_done_to_complete(mock_task_yaml, monkeypatch):
    item_id, task_path, base_dir = mock_task_yaml
    monkeypatch.setattr(handoff, "BASE_DIR", str(base_dir))
    
    handoff.record_handoff(item_id, "build", "done", from_task="TASK-001")
    
    with task_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    assert data["task_progress"]["TASK-001"] == "complete"

def test_handoff_maps_passed_to_complete(mock_task_yaml, monkeypatch):
    item_id, task_path, base_dir = mock_task_yaml
    monkeypatch.setattr(handoff, "BASE_DIR", str(base_dir))
    
    handoff.record_handoff(item_id, "test", "passed", from_task="TASK-001")
    
    with task_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    assert data["task_progress"]["TASK-001"] == "complete"

def test_handoff_maps_approved_to_complete(mock_task_yaml, monkeypatch):
    item_id, task_path, base_dir = mock_task_yaml
    monkeypatch.setattr(handoff, "BASE_DIR", str(base_dir))
    
    handoff.record_handoff(item_id, "review", "approved", from_task="TASK-001")
    
    with task_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    assert data["task_progress"]["TASK-001"] == "complete"
