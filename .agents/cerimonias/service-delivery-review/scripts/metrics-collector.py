#!/usr/bin/env python3
"""
Coleta métricas Kanban do diretório done/ e gera relatório de review.

Paths resolvidos em ordem de prioridade:
  1. Variável de ambiente KANBAN_ROOT  (ex: export KANBAN_ROOT=/home/x/proj/.agents/kanban)
  2. Auto-detecção: sobe a árvore de diretórios procurando .agents/kanban/board.yaml
  3. Fallback: .agents/kanban/ relativo ao Cwd
"""

import os
import yaml, json
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def _resolve_kanban_root() -> Path:
    """Resolve o diretório kanban/ de forma robusta independente do Cwd."""
    env = os.environ.get("KANBAN_ROOT")
    if env:
        return Path(env)

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".agents" / "kanban"
        if (candidate / "board.yaml").exists():
            return candidate

    return Path(".agents/kanban")


_KANBAN_ROOT = _resolve_kanban_root()
DONE_DIR = _KANBAN_ROOT / "done"
REVIEW_DIR = _KANBAN_ROOT / "reviews"

def parse_task(task_dir: Path):
    meta_file = task_dir / "task.yaml"
    if not meta_file.exists():
        return None
    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))

    phases = meta.get("phases", {})

    # Calcular tempos
    lead_time = None
    cycle_time = None

    if phases.get("discovery", {}).get("done") and phases.get("ship", {}).get("done"):
        start = phases["discovery"]["date"]
        end = phases["ship"]["date"]
        # Simplificado: assumindo formato ISO
        # Em produção usar dateutil
        lead_time = f"{start} -> {end}"

    if phases.get("build", {}).get("started") and phases.get("ship", {}).get("done"):
        start = phases["build"]["started"]
        end = phases["ship"]["done"]
        cycle_time = f"{start} -> {end}"

    return {
        "id": meta.get("id", task_dir.name),
        "title": meta.get("title", "Unknown"),
        "class": meta.get("class", "Standard"),
        "lead_time": lead_time,
        "cycle_time": cycle_time,
        "phases_completed": sum(1 for p in phases.values() if p.get("done"))
    }

def collect():
    tasks = [parse_task(d) for d in DONE_DIR.iterdir() if d.is_dir()]
    tasks = [t for t in tasks if t]

    total = len(tasks)
    by_class = defaultdict(int)
    for t in tasks:
        by_class[t["class"]] += 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "period": "last_30_days",  # simplificado
        "throughput": total,
        "by_class": dict(by_class),
        "tasks": tasks,
        "insights": [
            "Calcular Lead Time e Cycle Time requer parsing de datas (use dateutil em produção)",
            "Gerar CFD requer histórico diário do board (não apenas done/)"
        ]
    }

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    (REVIEW_DIR / f"review-{today}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"=== SERVICE DELIVERY REVIEW ===")
    print(f"Period: last 30 days")
    print(f"Throughput: {total} items")
    for cls, count in by_class.items():
        print(f"  {cls}: {count}")
    print(f"Report saved to: kanban/reviews/review-{today}.json")

if __name__ == "__main__":
    collect()
