#!/usr/bin/env python3
"""
Detecta itens parados no Kanban por mais que o threshold configurado.
"""

import yaml, json
from pathlib import Path
from datetime import datetime, timedelta

KANBAN_DIR = Path(".agents/kanban/in-progress")
CONFIG = Path(".agents/swarm.yaml")
LOG_DIR = Path(".agents/kanban/daily-logs")

def load_config():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    return data.get("thresholds", {})

def get_last_activity(task_dir: Path) -> datetime:
    latest = datetime.min
    for file in task_dir.rglob("*"):
        if file.is_file():
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if mtime > latest:
                latest = mtime
    return latest

def detect():
    cfg = load_config()
    alert_h = cfg.get("alert_idle_hours", 4)
    blocked_h = cfg.get("blocked_idle_hours", 8)

    now = datetime.now()
    alerts = []
    blocked = []

    for task_dir in KANBAN_DIR.iterdir():
        if not task_dir.is_dir():
            continue

        last = get_last_activity(task_dir)
        idle = now - last

        meta_file = task_dir / "task.yaml"
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}

        item = {
            "id": meta.get("id", task_dir.name),
            "owner": meta.get("owner", "unknown"),
            "phase": meta.get("current_phase", "unknown"),
            "idle_hours": round(idle.total_seconds() / 3600, 1),
            "last_activity": last.isoformat()
        }

        if idle > timedelta(hours=blocked_h):
            blocked.append(item)
        elif idle > timedelta(hours=alert_h):
            alerts.append(item)

    # Log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log = {
        "date": today,
        "alerts": alerts,
        "blocked": blocked,
        "action_items": [f"Escalate {b['id']} (owner: {b['owner']})" for b in blocked]
    }
    (LOG_DIR / f"{today}.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")

    print(f"=== DAILY FLOW ===")
    print(f"Date: {today}")
    print(f"Alerts (> {alert_h}h idle): {len(alerts)}")
    for a in alerts:
        print(f"  🟡 {a['id']} | {a['owner']} | {a['phase']} | {a['idle_hours']}h")
    print(f"Blocked (> {blocked_h}h idle): {len(blocked)}")
    for b in blocked:
        print(f"  🔴 {b['id']} | {b['owner']} | {b['phase']} | {b['idle_hours']}h")

if __name__ == "__main__":
    detect()
