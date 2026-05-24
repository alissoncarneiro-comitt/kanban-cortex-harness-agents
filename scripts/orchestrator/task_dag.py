#!/usr/bin/env python3
"""
task_dag.py — Parse _Depends_ from tasks.md and compute ready task sets.

FEAT-011 TASK-007.
"""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Mapping

_TASK_HEADER = re.compile(r"^##\s+(TASK-\d+)\s*:", re.MULTILINE)
_DEPENDS_LINE = re.compile(r"^_Depends_:\s*(.+?)\s*$", re.MULTILINE)
_NONE_MARKERS = frozenset({"nenhum", "nenhuma", "none", "—", "-", ""})


class TaskDagError(ValueError):
    """Erro de parse ou dependência inválida no DAG de tasks."""


class TaskDagCycleError(TaskDagError):
    """Ciclo detectado em _Depends_."""


def _normalize_dep_token(token: str) -> str:
    token = token.strip()
    if token.upper().startswith("TASK-"):
        return token.upper().replace("task-", "TASK-")
    match = re.match(r"TASK-?(\d+)", token, re.IGNORECASE)
    if match:
        return f"TASK-{int(match.group(1)):03d}"
    return token


def _parse_depends_value(raw: str) -> list[str]:
    lowered = raw.strip().lower()
    if lowered in _NONE_MARKERS:
        return []
    parts = re.split(r",|\+| e | and ", raw, flags=re.IGNORECASE)
    deps: list[str] = []
    for part in parts:
        part = part.strip()
        if not part or part.lower() in _NONE_MARKERS:
            continue
        deps.append(_normalize_dep_token(part))
    return deps


def _task_sort_key(task_id: str) -> tuple[int, str]:
    match = re.search(r"(\d+)", task_id)
    if match:
        return (int(match.group(1)), task_id)
    return (0, task_id)


def _extract_sections(content: str) -> dict[str, str]:
    """Mapa task_id -> bloco de texto da secção."""
    headers = list(_TASK_HEADER.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(headers):
        task_id = match.group(1).upper()
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
        sections[task_id] = content[start:end]
    return sections


def parse_tasks_md_content(content: str) -> dict[str, list[str]]:
    """Parse tasks.md → {task_id: [dependency_ids]}."""
    sections = _extract_sections(content)
    if not sections:
        raise TaskDagError("Nenhuma secção ## TASK-NNN encontrada em tasks.md")

    graph: dict[str, list[str]] = {}
    for task_id, body in sections.items():
        match = _DEPENDS_LINE.search(body)
        if not match:
            raise TaskDagError(f"{task_id}: linha _Depends_ ausente")
        graph[task_id] = _parse_depends_value(match.group(1))

    all_ids = set(graph)
    for task_id, deps in graph.items():
        for dep in deps:
            if dep not in all_ids:
                raise TaskDagError(
                    f"{task_id}: dependência desconhecida '{dep}' (não existe em tasks.md)"
                )

    _assert_acyclic(graph)
    return graph


def parse_tasks_md(path: str | Path) -> dict[str, list[str]]:
    """Lê ficheiro tasks.md e devolve o grafo de dependências."""
    file_path = Path(path)
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskDagError(f"Não foi possível ler {file_path}: {exc}") from exc
    return parse_tasks_md_content(content)


def _assert_acyclic(graph: Mapping[str, list[str]]) -> None:
    indegree = {node: 0 for node in graph}
    for node, deps in graph.items():
        indegree[node] = len(deps)

    queue: deque[str] = deque(n for n, deg in indegree.items() if deg == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for other, deps in graph.items():
            if node in deps:
                indegree[other] -= 1
                if indegree[other] == 0:
                    queue.append(other)

    if visited != len(graph):
        cycle_nodes = [n for n, deg in indegree.items() if deg > 0]
        raise TaskDagCycleError(
            f"Ciclo em _Depends_: envolvidos {sorted(cycle_nodes)}"
        )


def ready_tasks(
    graph: Mapping[str, list[str]],
    progress: set[str],
) -> list[str]:
    """Tasks com todas as dependências satisfeitas e ainda não em progress."""
    done = set(progress)
    ready: list[str] = []
    for task_id, deps in graph.items():
        if task_id in done:
            continue
        if all(dep in done for dep in deps):
            ready.append(task_id)
    return sorted(ready, key=_task_sort_key)
