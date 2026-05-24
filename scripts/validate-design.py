#!/usr/bin/env python3
"""Validate harness design.md artifacts."""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from artifact_schema import parse_markdown_sections


REQUIRED_SECTIONS = (
    "Context Diagram",
    "Data Flow",
    "File Structure Plan",
    "State Machine",
    "Error Handling Matrix",
    "Security Considerations",
    "Performance Budget",
    "Test Strategy",
    "Handoff para Proxima Fase",
)


def _read_artifact(path: Path) -> tuple[str | None, int]:
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        return None, 2
    try:
        return path.read_text(encoding="utf-8"), 0
    except OSError as exc:
        print(f"cannot read: {path}: {exc}", file=sys.stderr)
        return None, 2


def _normalize_heading(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def validate_design_document(markdown: str, artifact_name: str) -> list[str]:
    present = {_normalize_heading(section.title) for section in parse_markdown_sections(markdown)}
    errors: list[str] = []
    for section in REQUIRED_SECTIONS:
        if _normalize_heading(section) not in present:
            errors.append(f"ERROR {artifact_name} missing section: {section}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate design.md artifact schema.")
    parser.add_argument("artifact", help="Path to design.md")
    args = parser.parse_args(argv)

    path = Path(args.artifact)
    content, status = _read_artifact(path)
    if status != 0 or content is None:
        return status

    errors = validate_design_document(content, path.name)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(f"OK {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
