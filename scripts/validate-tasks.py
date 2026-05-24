#!/usr/bin/env python3
"""Validate harness tasks.md artifacts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from artifact_schema import validate_tasks_document


def _read_artifact(path: Path) -> tuple[str | None, int]:
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        return None, 2
    try:
        return path.read_text(encoding="utf-8"), 0
    except OSError as exc:
        print(f"cannot read: {path}: {exc}", file=sys.stderr)
        return None, 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate tasks.md artifact schema.")
    parser.add_argument("artifact", help="Path to tasks.md")
    args = parser.parse_args(argv)

    path = Path(args.artifact)
    content, status = _read_artifact(path)
    if status != 0 or content is None:
        return status

    diagnostics = validate_tasks_document(content, artifact_name=path.name)
    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic.format())
        return 1

    print(f"OK {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
