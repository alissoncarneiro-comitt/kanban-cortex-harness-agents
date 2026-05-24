"""
Audit log exporter for Agent Harness — FEAT-002 TASK-005.

Reads audit.jsonl and exports JSONL or CSV with optional filters.
Filters combine with AND logic.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# All known schema fields (defines CSV column order)
_SCHEMA_FIELDS = [
    "event_type", "timestamp_iso", "item_id", "phase",
    "actor", "model_id", "provider", "session_id",
    "tokens_input", "tokens_output", "tokens_cache_read", "tokens_cache_write",
    "context_window_used_pct",
    "status", "artifacts_produced", "rejection_count", "escalated",
    "reason_summary", "decision",
]


def export(
    audit_path: Path,
    output_path: Path,
    fmt: str = "jsonl",
    item_id: str | None = None,
    phase: str | None = None,
    model_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    """Export filtered audit entries. Returns count of exported entries."""
    entries = _load_and_filter(audit_path, item_id, phase, model_id, date_from, date_to)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "jsonl":
        _write_jsonl(output_path, entries)
    elif fmt == "csv":
        _write_csv(output_path, entries)
    else:
        raise ValueError(f"Unknown format '{fmt}'. Use 'jsonl' or 'csv'.")

    return len(entries)


def _load_and_filter(
    path: Path,
    item_id: str | None,
    phase: str | None,
    model_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[dict[str, Any]]:
    results = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return results

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if item_id and entry.get("item_id") != item_id:
            continue
        if phase and entry.get("phase") != phase:
            continue
        if model_id and entry.get("model_id") != model_id:
            continue
        if date_from or date_to:
            ts = _parse_ts(entry.get("timestamp_iso"))
            if ts is None:
                continue
            if date_from and ts < date_from:
                continue
            if date_to and ts > date_to:
                continue

        results.append(entry)

    return results


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _strip_sensitive(entry: dict) -> dict:
    """Remove fields prefixed with '_sensitive_' before export."""
    return {k: v for k, v in entry.items() if not k.startswith("_sensitive_")}


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    lines = [json.dumps(_strip_sensitive(e), ensure_ascii=False, default=str) for e in entries]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_csv(path: Path, entries: list[dict]) -> None:
    # Collect all unique fields: schema first, then any extras (excluding _sensitive_)
    extra = set()
    for e in entries:
        extra.update(k for k in e.keys() if not k.startswith("_sensitive_"))
    fields = _SCHEMA_FIELDS + sorted(extra - set(_SCHEMA_FIELDS))

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            clean = _strip_sensitive(entry)
            row = {f: clean.get(f, "") for f in fields}
            writer.writerow(row)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export audit.jsonl to JSONL or CSV")
    parser.add_argument("--audit", default=".agents/kanban/audit/audit.jsonl")
    parser.add_argument("--format", dest="fmt", choices=["jsonl", "csv"], default="jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--item")
    parser.add_argument("--phase")
    parser.add_argument("--model")
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    args = parser.parse_args()

    df = datetime.fromisoformat(args.date_from) if args.date_from else None
    dt = datetime.fromisoformat(args.date_to)   if args.date_to   else None

    count = export(
        Path(args.audit), Path(args.output),
        fmt=args.fmt,
        item_id=args.item,
        phase=args.phase,
        model_id=args.model,
        date_from=df,
        date_to=dt,
    )
    print(f"Exported {count} entries to {args.output}")
