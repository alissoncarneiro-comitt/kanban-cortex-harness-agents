#!/usr/bin/env python3
"""Validate harness requirements.md artifacts."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from artifact_schema import parse_markdown_sections


REQ_RE = re.compile(r"^REQ-(\d{3})\b")


def _read_artifact(path: Path) -> tuple[str | None, int]:
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        return None, 2
    try:
        return path.read_text(encoding="utf-8"), 0
    except OSError as exc:
        print(f"cannot read: {path}: {exc}", file=sys.stderr)
        return None, 2


def _requirement_ids(markdown: str) -> list[str]:
    ids: list[str] = []
    for section in parse_markdown_sections(markdown):
        match = REQ_RE.match(section.title.strip())
        if match:
            ids.append(f"REQ-{match.group(1)}")
    return ids


def _traceability_body(markdown: str) -> str:
    for section in parse_markdown_sections(markdown):
        if section.title.strip().lower() == "traceability matrix":
            return section.body
    return ""


def _has_ears_sentence(body: str) -> bool:
    return bool(re.search(r"\bshall\b.+\bwhen\b", body, flags=re.IGNORECASE | re.DOTALL))


def validate_requirements_document(markdown: str, artifact_name: str) -> list[str]:
    errors: list[str] = []
    traceability = _traceability_body(markdown)

    for section in parse_markdown_sections(markdown):
        match = REQ_RE.match(section.title.strip())
        if not match:
            continue

        req_id = f"REQ-{match.group(1)}"
        if not _has_ears_sentence(section.body):
            errors.append(f"ERROR {artifact_name} {req_id} missing EARS shall/when sentence")
        for label in ("Acceptance Criteria", "Boundary", "Depends"):
            if label.lower() not in section.body.lower():
                errors.append(f"ERROR {artifact_name} {req_id} missing {label}")

    for req_id in _requirement_ids(markdown):
        if req_id not in traceability:
            errors.append(f"ERROR {artifact_name} {req_id} missing traceability row")

    if not traceability:
        errors.append(f"ERROR {artifact_name} missing section: Traceability Matrix")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate requirements.md artifact schema.")
    parser.add_argument("artifact", help="Path to requirements.md")
    args = parser.parse_args(argv)

    path = Path(args.artifact)
    content, status = _read_artifact(path)
    if status != 0 or content is None:
        return status

    errors = validate_requirements_document(content, path.name)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(f"OK {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
