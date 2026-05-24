"""
Metrics collector for Agent Harness audit trail — FEAT-002 TASK-003.

Reads audit.jsonl and produces:
  - lead-time.yaml  : lead time, cycle time, queue time, flow efficiency
  - token-usage.yaml: token totals, cache hit rate, efficiency by phase, context pressure
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect(audit_path: Path, item_id: str, out_dir: Path) -> None:
    """Parse audit.jsonl for item_id and write metrics YAML files."""
    entries = _load_entries(audit_path, item_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    lt_data = _compute_lead_time(entries)
    tu_data = _compute_token_usage(entries)

    _write_yaml(out_dir / "lead-time.yaml", lt_data)
    _write_yaml(out_dir / "token-usage.yaml", tu_data)

    if tu_data.get("context_pressure_max_pct", 0) and tu_data["context_pressure_max_pct"] > 80:
        print(f"ALERT: context_pressure_max_pct={tu_data['context_pressure_max_pct']:.1f}% > 80% "
              f"for item {item_id}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_entries(path: Path, item_id: str) -> list[dict[str, Any]]:
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("item_id") == item_id:
                    entries.append(e)
            except json.JSONDecodeError:
                pass
    except FileNotFoundError:
        pass
    return entries


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    delta = (b - a).total_seconds()
    return round(delta / 3600, 4)


def _compute_lead_time(entries: list[dict]) -> dict:
    # Collect phase_start and phase_end timestamps keyed by phase
    starts: dict[str, datetime] = {}
    ends: dict[str, datetime] = {}

    for e in entries:
        et = e.get("event_type")
        phase = e.get("phase")
        ts = _parse_ts(e.get("timestamp_iso"))
        if not phase or not ts:
            continue
        if et == "phase_start":
            if phase not in starts or ts < starts[phase]:
                starts[phase] = ts
        elif et == "phase_end":
            if phase not in ends or ts > ends[phase]:
                ends[phase] = ts

    # Lead time: first phase_start → last phase_end across all phases
    all_starts = list(starts.values())
    all_ends = list(ends.values())
    first_start = min(all_starts) if all_starts else None
    last_end = max(all_ends) if all_ends else None
    lead_time_h = _hours(first_start, last_end)

    # Cycle time per phase
    phases_ordered = [p for p in starts if p in ends]
    phases_ordered.sort(key=lambda p: starts[p])

    cycle_time: dict[str, float] = {}
    for p in phases_ordered:
        h = _hours(starts[p], ends[p])
        if h is not None:
            cycle_time[p] = round(h, 4)

    # Queue time: gap between end of previous phase and start of current
    queue_time: dict[str, float] = {}
    for i, p in enumerate(phases_ordered[1:], 1):
        prev_phase = phases_ordered[i - 1]
        if prev_phase in ends and p in starts:
            q = _hours(ends[prev_phase], starts[p])
            if q is not None:
                queue_time[p] = round(q, 4)

    # Flow efficiency = Σ cycle_time / lead_time
    total_cycle = sum(cycle_time.values())
    flow_efficiency = None
    if lead_time_h and lead_time_h > 0:
        flow_efficiency = round(total_cycle / lead_time_h * 100, 2)

    return {
        "item_id": None,
        "lead_time_h": lead_time_h,
        "cycle_time_by_phase": cycle_time,
        "queue_time_by_phase": queue_time,
        "flow_efficiency_pct": flow_efficiency,
    }


def _compute_token_usage(entries: list[dict]) -> dict:
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    max_context_pct = 0.0

    phase_input: dict[str, int] = {}
    phase_output: dict[str, int] = {}
    model_input: dict[str, int] = {}
    model_output: dict[str, int] = {}

    for e in entries:
        if e.get("event_type") != "phase_end":
            continue
        phase = e.get("phase", "unknown")
        model = e.get("model_id", "unknown")

        ti = e.get("tokens_input") or 0
        to = e.get("tokens_output") or 0
        tcr = e.get("tokens_cache_read") or 0
        tcw = e.get("tokens_cache_write") or 0
        ctx = e.get("context_window_used_pct") or 0.0

        total_input += ti
        total_output += to
        total_cache_read += tcr
        total_cache_write += tcw
        if ctx * 100 > max_context_pct:
            max_context_pct = ctx * 100

        phase_input[phase] = phase_input.get(phase, 0) + ti
        phase_output[phase] = phase_output.get(phase, 0) + to
        model_input[model] = model_input.get(model, 0) + ti
        model_output[model] = model_output.get(model, 0) + to

    # Cache hit rate = cache_read / (cache_read + input) * 100
    denom = total_cache_read + total_input
    cache_hit_rate = round(total_cache_read / denom * 100, 2) if denom > 0 else 0.0

    # Token efficiency by phase
    token_eff: dict[str, float] = {}
    for p in phase_input:
        if phase_input[p] > 0:
            token_eff[p] = round(phase_output.get(p, 0) / phase_input[p], 4)

    # Model breakdown
    model_breakdown: dict[str, dict] = {}
    for m in model_input:
        model_breakdown[m] = {
            "tokens_input": model_input[m],
            "tokens_output": model_output.get(m, 0),
        }

    return {
        "tokens_total_input": total_input,
        "tokens_total_output": total_output,
        "tokens_total_cache_read": total_cache_read,
        "tokens_total_cache_write": total_cache_write,
        "cache_hit_rate_pct": cache_hit_rate,
        "token_efficiency_by_phase": token_eff,
        "context_pressure_max_pct": round(max_context_pct, 2),
        "model_breakdown": model_breakdown,
    }


def _write_yaml(path: Path, data: dict) -> None:
    if _HAS_YAML:
        path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False),
                        encoding="utf-8")
    else:
        # Fallback: minimal YAML-compatible serialisation
        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"{k}:")
                for sk, sv in v.items():
                    lines.append(f"  {sk}: {sv}")
            else:
                lines.append(f"{k}: {v}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect metrics from audit.jsonl")
    parser.add_argument("--audit", default=".agents/kanban/audit/audit.jsonl")
    parser.add_argument("--item", required=True)
    parser.add_argument("--out", default=".agents/kanban/metrics")
    args = parser.parse_args()

    collect(Path(args.audit), args.item, Path(args.out))
    print(f"Metrics written to {args.out}/")
