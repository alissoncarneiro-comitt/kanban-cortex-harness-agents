"""
Append-only audit writer for Agent Harness — FEAT-002.

Single responsibility: emit structured JSONL events to audit.jsonl.
Non-blocking: I/O errors are logged to stderr, never raised to callers.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_EVENT_TYPES = frozenset({
    "phase_start",
    "phase_end",
    "human_approval",
    "review_rejection",
    "phase_blocked",
})

REQUIRED_FIELDS = frozenset({"item_id", "session_id"})

# Fields that are nullable/optional per event_type
_NULLABLE_FIELDS = frozenset({
    "tokens_input", "tokens_output", "tokens_cache_read",
    "tokens_cache_write", "context_window_used_pct",
    "status", "artifacts_produced", "rejection_count",
    "escalated", "reason_summary", "decision",
    "model_id", "provider", "actor", "phase",
})


class AuditWriter:
    def __init__(self, audit_path: Path | str) -> None:
        self._path = Path(audit_path)
        # (session_id, event_type) pairs already written — dedup guard
        self._seen: set[tuple[str, str]] = set()

    def emit_event(self, event_type: str, **fields: Any) -> None:
        """Append one audit entry. Never raises — errors go to stderr."""
        try:
            self._validate(event_type, fields)
            entry = self._build_entry(event_type, fields)
            dedup_key = (str(fields.get("session_id", "")), event_type)
            if dedup_key in self._seen:
                return
            self._append(entry)
            self._seen.add(dedup_key)
        except ValueError:
            raise
        except Exception as exc:
            print(f"[audit_writer] ERROR: {exc}", file=sys.stderr)

    def _validate(self, event_type: str, fields: dict[str, Any]) -> None:
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event_type '{event_type}' invalid. "
                f"Must be one of: {sorted(VALID_EVENT_TYPES)}"
            )
        missing = REQUIRED_FIELDS - fields.keys()
        if missing:
            raise ValueError(f"Required fields missing: {sorted(missing)}")

    def _build_entry(self, event_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "event_type": event_type,
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        }
        # Nullable token/context fields default to None
        for f in _NULLABLE_FIELDS:
            entry[f] = fields.get(f)
        # All other caller-supplied fields
        for k, v in fields.items():
            entry[k] = v
        return entry

    def _append(self, entry: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        # Security: restrict to owner-rw, group-r
        try:
            self._path.chmod(0o640)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Module-level convenience — default writer using project-relative path
# ---------------------------------------------------------------------------

_DEFAULT_PATH = Path(__file__).parent.parent / ".agents" / "kanban" / "audit" / "audit.jsonl"
_default_writer: AuditWriter | None = None


def _get_default() -> AuditWriter:
    global _default_writer
    if _default_writer is None:
        _default_writer = AuditWriter(_DEFAULT_PATH)
    return _default_writer


def emit_event(event_type: str, **fields: Any) -> None:
    """Module-level emit using the default project audit path."""
    _get_default().emit_event(event_type, **fields)
