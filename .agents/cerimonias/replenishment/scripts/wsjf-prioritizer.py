#!/usr/bin/env python3
"""
Weighted Shortest Job First (WSJF) para priorização do backlog.
Lê kanban/backlog/*/business-case.md e recalcula scores.
"""

import yaml, json, re
from pathlib import Path
from datetime import datetime

BACKLOG_DIR = Path(".agents/kanban/backlog")

def parse_business_case(path: Path):
    """Extrai métricas do business-case.md (YAML frontmatter ou seções)."""
    text = path.read_text(encoding="utf-8")
    # Tenta extrair YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1])
                return meta
            except Exception:
                pass
    # Fallback: regex simples
    data = {}
    for line in text.splitlines():
        if m := re.match(r"(?i)(business_value|risk_reduction|time_criticality|estimated_effort):\s*(\d+)", line):
            data[m.group(1).lower()] = int(m.group(2))
    return data

def calculate_wsjf(item_dir: Path):
    bc = item_dir / "business-case.md"
    if not bc.exists():
        return None
    data = parse_business_case(bc)
    if not data:
        return None

    cod = data.get("business_value", 0) + data.get("risk_reduction", 0) + data.get("time_criticality", 0)
    job_size = data.get("estimated_effort", 1)
    if job_size <= 0:
        job_size = 1

    return {
        "id": item_dir.name,
        "wsjf_score": cod / job_size,
        "cost_of_delay": cod,
        "job_size": job_size,
        "last_calculated": datetime.now().isoformat()
    }

def prioritize():
    items = []
    for item_dir in BACKLOG_DIR.iterdir():
        if item_dir.is_dir():
            result = calculate_wsjf(item_dir)
            if result:
                items.append(result)

    items.sort(key=lambda x: x["wsjf_score"], reverse=True)

    # Salvar ranking
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_items": len(items),
        "ranking": items
    }

    out_path = Path("kanban/backlog-ranking.json")
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    print(f"=== BACKLOG RANKING (WSJF) ===")
    print(f"Total items: {len(items)}")
    for i, item in enumerate(items[:10], 1):
        print(f"{i}. {item['id']} | Score: {item['wsjf_score']:.2f} | CoD: {item['cost_of_delay']} | Size: {item['job_size']}h")

    return items

if __name__ == "__main__":
    prioritize()
