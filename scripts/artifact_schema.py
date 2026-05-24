#!/usr/bin/env python3
"""Shared Markdown artifact schema validation primitives."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MarkdownSection:
    level: int
    title: str
    body: str
    line: int


@dataclass(frozen=True)
class Diagnostic:
    artifact: str
    location: str
    message: str

    def format(self) -> str:
        return f"ERROR {self.artifact} {self.location} {self.message}"


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TASK_RE = re.compile(r"^(?:TASK[-\s]*(\d+)|Task\s+(\d+))\b", re.IGNORECASE)

TASK_REQUIRED_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("_Acceptance_", ("_Acceptance_", "Acceptance")),
    ("_Boundary_", ("_Boundary_", "Boundary")),
    ("_Depends_", ("_Depends_", "Depends")),
    ("_Estimativa_", ("_Estimativa_", "Estimativa", "Estimate")),
)


def parse_markdown_sections(markdown: str) -> list[MarkdownSection]:
    """Return Markdown heading sections with their nested body text."""
    headings: list[tuple[int, str, int, int]] = []
    lines = markdown.splitlines()

    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        headings.append((len(match.group(1)), match.group(2).strip(), index, index + 1))

    sections: list[MarkdownSection] = []
    for position, (level, title, heading_index, line_number) in enumerate(headings):
        body_end = len(lines)
        for next_level, _next_title, next_index, _next_line_number in headings[position + 1 :]:
            if next_level <= level:
                body_end = next_index
                break

        body = "\n".join(lines[heading_index + 1 : body_end]).strip("\n")
        sections.append(MarkdownSection(level=level, title=title, body=body, line=line_number))

    return sections


def validate_tasks_document(markdown: str, *, artifact_name: str = "tasks.md") -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for section in parse_markdown_sections(markdown):
        task_id = _task_id(section.title)
        if task_id is None:
            continue

        searchable = f"{section.title}\n{section.body}"
        for field_name, aliases in TASK_REQUIRED_FIELDS:
            if not _contains_any_field(searchable, aliases):
                diagnostics.append(Diagnostic(artifact_name, task_id, f"missing {field_name}"))

    return diagnostics


def _task_id(title: str) -> str | None:
    match = TASK_RE.match(title.strip())
    if not match:
        return None

    number = match.group(1) or match.group(2)
    return f"TASK-{int(number):03d}"


def _contains_any_field(text: str, aliases: tuple[str, ...]) -> bool:
    for alias in aliases:
        label = alias.strip("_")
        escaped = re.escape(label)
        if re.search(rf"(?:^|\n)\s*(?:[#*-]+\s*)?(?:\*\*)?_?{escaped}:?_?(?:\*\*)?\s*:?", text):
            return True
    return False
