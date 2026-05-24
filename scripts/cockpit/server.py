"""
cockpit server — Kanban Board Online HTTP server (FEAT-008)

Endpoints:
  GET /              → serve src/cockpit/board.html
  GET /api/board     → retorna board.yaml como JSON
  GET /api/events    → SSE stream com updates do board

Porta padrão: 8337 (configurável via COCKPIT_PORT env var)
Escuta apenas em 127.0.0.1 (localhost).

Usa PyYAML quando disponível; caso contrário usa parser YAML mínimo local.
Feature flag: COCKPIT_ENABLED — se não definida, servidor roda normalmente.
"""

import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

# Tenta importar PyYAML. A flag de teste força o parser stdlib.
try:
    if os.environ.get("COCKPIT_SIMULATE_NO_PYYAML") == "1":
        raise ImportError("simulated PyYAML absence")
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

# ===== Constantes =====

DEFAULT_PORT = 8337
DEFAULT_HOST = "127.0.0.1"

_THIS_FILE = Path(__file__).resolve()

# Global install: ~/.kanban-cortex-harness-agents/cockpit/server.py  → board.html is a sibling
# Legacy install: <project>/scripts/cockpit/server.py → board.html at <project>/src/cockpit/
_SIBLING_HTML = _THIS_FILE.parent / "board.html"
if _SIBLING_HTML.exists():
    # Running from ~/.kanban-cortex-harness-agents/cockpit/ (global) or any flat layout
    DEFAULT_HTML_PATH = _SIBLING_HTML
    PROJECT_ROOT = Path.cwd()          # project is wherever we're invoked from
else:
    # Legacy layout: 3 levels up from scripts/cockpit/server.py
    PROJECT_ROOT = _THIS_FILE.parent.parent.parent
    DEFAULT_HTML_PATH = PROJECT_ROOT / "src" / "cockpit" / "board.html"

# Board path is always relative to the current project (CWD)
DEFAULT_BOARD_PATH = Path(".agents") / "kanban" / "board.yaml"

# ===== Estado compartilhado (SSE subscribers) =====

_subscribers_lock = threading.Lock()
_subscribers: list = []          # lista de (queue-like) response objects
_board_cache: dict | None = None  # última versão válida do board
_board_cache_lock = threading.Lock()


# ===== Leitura do board YAML =====

def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    escaped = False
    out = []
    for char in line:
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            out.append(char)
            escaped = True
            continue
        if char in ("'", '"'):
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
        if char == "#" and in_quote is None:
            break
        out.append(char)
    return "".join(out).rstrip()


def _prepare_yaml_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        without_comment = _strip_comment(raw)
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip(" "))
        lines.append((indent, without_comment.strip()))
    return lines


def _parse_scalar(value: str):
    value = value.strip()
    if value in ("", "null", "Null", "NULL", "~"):
        return None
    if value in ("[]",):
        return []
    if value in ("{}",):
        return {}
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"YAML inválido: esperado chave: valor em '{text}'")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _next_container(lines: list[tuple[int, str]], index: int, indent: int):
    if index >= len(lines) or lines[index][0] <= indent:
        return None, index
    return _parse_block(lines, index, lines[index][0])


def _parse_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict, int]:
    data: dict = {}
    while index < len(lines):
        current_indent, text = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"YAML inválido: indentação inesperada em '{text}'")
        if text.startswith("- "):
            break
        key, value = _split_key_value(text)
        index += 1
        if value:
            data[key] = _parse_scalar(value)
        else:
            child, index = _next_container(lines, index, indent)
            data[key] = child
    return data, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list, int]:
    items: list = []
    while index < len(lines):
        current_indent, text = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"YAML inválido: indentação inesperada em '{text}'")
        if not text.startswith("- "):
            break
        rest = text[2:].strip()
        index += 1
        if not rest:
            child, index = _next_container(lines, index, indent)
            items.append(child)
            continue
        if ":" in rest:
            key, value = _split_key_value(rest)
            item: dict = {}
            if value:
                item[key] = _parse_scalar(value)
            else:
                child, index = _next_container(lines, index, indent)
                item[key] = child
            if index < len(lines) and lines[index][0] > indent:
                extra, index = _parse_dict(lines, index, lines[index][0])
                item.update(extra)
            items.append(item)
        else:
            items.append(_parse_scalar(rest))
    return items, index


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int):
    if index >= len(lines):
        return None, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def parse_yaml_minimal(text: str) -> dict:
    lines = _prepare_yaml_lines(text)
    if not lines:
        raise ValueError("board.yaml is empty")
    data, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError("YAML inválido: conteúdo não processado")
    if not isinstance(data, dict):
        raise ValueError("YAML inválido: raiz deve ser objeto")
    return data


def read_board(board_path: str | Path) -> tuple[dict | None, str | None]:
    """
    Lê e parseia board.yaml.

    Retorna:
        (dict, None)       — sucesso
        (None, str)        — erro, com mensagem de erro
    """
    path = Path(board_path)
    if not path.exists():
        return None, "board.yaml not found"

    try:
        text = path.read_text(encoding="utf-8")
        if YAML_AVAILABLE:
            data = yaml.safe_load(text)
        else:
            data = parse_yaml_minimal(text)
        if data is None:
            return None, "board.yaml is empty"
        return data, None
    except Exception as exc:
        if YAML_AVAILABLE and hasattr(yaml, "YAMLError") and isinstance(exc, yaml.YAMLError):
            return None, f"YAML parse error: {exc}"
        if isinstance(exc, OSError):
            return None, f"IO error reading board.yaml: {exc}"
        return None, f"YAML parse error: {exc}"


# ===== Projeção operacional de item =====

ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
TASK_HEADING_RE = re.compile(r"^##\s+(TASK-\d{3})\s*:\s*(.+?)\s*$", re.MULTILINE)
DONE_STATUSES = {"done", "completed", "complete", "approved", "passed", "shipped"}
PHASE_AGENT_MAP = {
    "discover": "a-discover",
    "requirements": "a-spec",
    "spec": "a-spec",
    "design": "a-design",
    "build": "a-build",
    "review": "a-review",
    "test": "a-test",
    "ship": "a-ship",
}
AGENT_STATUS_RANK = {"done": 0, "waiting": 1, "running": 2, "blocked": 3}
ARTIFACT_FILES = {
    "brief": ("brief.md", "Brief"),
    "requirements": ("requirements.md", "Requirements"),
    "design": ("design.md", "Design"),
    "tasks": ("tasks.md", "Tasks"),
    "acceptance": ("acceptance-criteria.md", "Acceptance"),
    "stakeholders": ("stakeholder-map.md", "Stakeholders"),
    "review": ("review-report.md", "Review"),
    "qa": ("qa-report.md", "QA Report"),
    "security": ("security-report.md", "Security"),
    "failure-modes": ("failure-modes-review.md", "Failure Modes"),
    "ship": ("ship-log.md", "Ship Log"),
}


def _operations_ui_enabled() -> bool:
    return os.environ.get("COCKPIT_OPERATIONS_UI", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _read_yaml_file(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, "not found"
    try:
        text = path.read_text(encoding="utf-8")
        if YAML_AVAILABLE:
            data = yaml.safe_load(text)
        else:
            data = parse_yaml_minimal(text)
        if data is None:
            return {}, None
        if not isinstance(data, dict):
            return None, f"YAML root must be object: {path.name}"
        return data, None
    except Exception as exc:
        return None, str(exc)


def _find_board_item(board_data: dict, item_id: str) -> tuple[dict | None, str | None]:
    board = board_data.get("board", {})
    items = board.get("items", {})
    if not isinstance(items, dict):
        return None, None
    for column, column_items in items.items():
        if not isinstance(column_items, list):
            continue
        for item in column_items:
            if isinstance(item, dict) and str(item.get("id", "")) == item_id:
                return item, str(column)
    return None, None


def _item_artifact_dir(board_path: Path, item_id: str) -> Path | None:
    kanban_dir = board_path.parent
    for lane in ("in-progress", "backlog", "done"):
        candidate = kanban_dir / lane / item_id
        if candidate.is_dir():
            return candidate
    return None


def _artifact_evidence(artifact_dir: Path | None) -> list[dict]:
    if artifact_dir is None:
        return []
    evidence = []
    for artifact_id, (filename, label) in ARTIFACT_FILES.items():
        path = artifact_dir / filename
        if path.is_file():
            evidence.append({
                "id": artifact_id,
                "label": label,
                "filename": filename,
                "size": path.stat().st_size,
            })
    return evidence


def _tasks_from_markdown(path: Path, default_status: str = "unknown") -> list[dict]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [
        {"id": match.group(1), "title": match.group(2).strip(), "status": default_status}
        for match in TASK_HEADING_RE.finditer(text)
    ]


def _tasks_from_task_yaml(task_data: dict) -> list[dict]:
    raw_tasks = task_data.get("tasks", [])
    if not isinstance(raw_tasks, list):
        return []
    tasks: list[dict] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("id", "")).strip()
        if not task_id:
            continue
        tasks.append({
            "id": task_id,
            "title": str(raw.get("title", "")).strip(),
            "status": str(raw.get("status", "unknown")).strip() or "unknown",
        })
    return tasks


def _merge_tasks(primary: list[dict], fallback: list[dict]) -> tuple[list[dict], str | None]:
    if primary:
        known = {task["id"] for task in primary}
        for task in fallback:
            if task["id"] not in known:
                primary.append(task)
        return primary, "task.yaml"
    if fallback:
        return fallback, "tasks.md"
    return [], None


def _apply_pipeline_task_status(tasks: list[dict], task_data: dict) -> list[dict]:
    """Infer per-task status from pipeline.current_task when tasks.md has no explicit status."""
    pipeline = task_data.get("pipeline") if isinstance(task_data.get("pipeline"), dict) else {}
    pipeline_status = str(pipeline.get("status", "")).lower()
    current_task = str(pipeline.get("current_task", "")).strip()

    if pipeline_status in DONE_STATUSES:
        return [dict(t, status="done") for t in tasks]

    if not current_task:
        return tasks

    ids = [t["id"] for t in tasks]
    if current_task not in ids:
        return tasks

    current_idx = ids.index(current_task)
    result = []
    for i, task in enumerate(tasks):
        if str(task.get("status", "")).lower() not in ("unknown", ""):
            result.append(task)
        elif i < current_idx:
            result.append(dict(task, status="done"))
        elif i == current_idx:
            result.append(dict(task, status="in_progress"))
        else:
            result.append(task)
    return result


def _progress(tasks: list[dict], source: str | None) -> dict:
    total = len(tasks)
    completed = sum(
        1 for task in tasks
        if str(task.get("status", "")).strip().lower() in DONE_STATUSES
    )
    percent = int(round((completed / total) * 100)) if total else 0
    return {
        "completed": completed,
        "total": total,
        "percent": percent,
        "source": source,
    }


def _normalize_agent_status(status: object) -> str:
    value = str(status or "").strip().lower()
    if value in {"blocked", "blocker", "failed", "failure", "error", "rejected"}:
        return "blocked"
    if value in {"running", "active", "working", "in-progress", "in_progress"}:
        return "running"
    if value in DONE_STATUSES:
        return "done"
    return "waiting"


def _phase_statuses(task_data: dict) -> dict[str, str]:
    statuses: dict[str, str] = {}
    phase_status = task_data.get("phase_status", {})
    if isinstance(phase_status, dict):
        for phase, status in phase_status.items():
            statuses[str(phase)] = _normalize_agent_status(status)

    phase_data = task_data.get("phases", {})
    if isinstance(phase_data, dict):
        for phase, data in phase_data.items():
            if isinstance(data, dict):
                if data.get("done") is True:
                    statuses[str(phase)] = "done"
                elif data.get("blocked") is True:
                    statuses[str(phase)] = "blocked"
                elif data.get("result"):
                    statuses[str(phase)] = _normalize_agent_status(data.get("result"))

    pipeline = task_data.get("pipeline", {})
    if isinstance(pipeline, dict) and pipeline.get("current_phase"):
        phase = str(pipeline["current_phase"])
        pipeline_status = _normalize_agent_status(pipeline.get("status"))
        if pipeline_status == "waiting" and pipeline.get("status") not in (None, "", "idle"):
            pipeline_status = "running"
        statuses[phase] = pipeline_status
    return statuses


def _agents_from_task_data(task_data: dict, item: dict) -> list[str]:
    agents = item.get("agents", task_data.get("agents", []))
    if isinstance(agents, str):
        agents = [agents]
    if not isinstance(agents, list):
        agents = []
    normalized = [str(agent).strip() for agent in agents if str(agent).strip()]
    if normalized:
        return normalized

    inferred: list[str] = []
    for phase in _phase_statuses(task_data):
        agent = PHASE_AGENT_MAP.get(str(phase).strip().lower())
        if agent and agent not in inferred:
            inferred.append(agent)
    return inferred


def _agent_statuses_from_task_data(task_data: dict, item: dict, agents: list[str]) -> list[dict]:
    status_by_agent: dict[str, str] = {}
    for phase, status in _phase_statuses(task_data).items():
        agent = PHASE_AGENT_MAP.get(str(phase).strip().lower())
        if not agent:
            continue
        previous = status_by_agent.get(agent)
        if previous is None or AGENT_STATUS_RANK[status] > AGENT_STATUS_RANK[previous]:
            status_by_agent[agent] = status

    item_status = _normalize_agent_status(item.get("status"))
    return [
        {"name": agent, "status": status_by_agent.get(agent, item_status)}
        for agent in agents
    ]


def _proposal_slug(summary: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", summary.strip().lower()).strip("-")
    return slug[:48] or "requirements-change"


def _clean_markdown_text(value: object) -> str:
    return str(value or "").replace("\x00", "").strip()


def create_requirement_proposal(
    board_path: str | Path,
    item_id: str,
    payload: dict,
) -> tuple[dict, int]:
    item_id = unquote(item_id).strip()
    if not ITEM_ID_RE.match(item_id):
        return {"error": "invalid item id"}, 400

    board_data, error = read_board(board_path)
    if error or board_data is None:
        return {"error": error or "board unavailable"}, 500
    item, _column = _find_board_item(board_data, item_id)
    if item is None:
        return {"error": f"item not found: {item_id}"}, 404

    artifact_dir = _item_artifact_dir(Path(board_path), item_id)
    if artifact_dir is None:
        return {"error": f"item artifacts not found: {item_id}"}, 404

    summary = _clean_markdown_text(payload.get("summary"))
    body = _clean_markdown_text(payload.get("body"))
    if not summary or not body:
        return {"error": "summary and body are required"}, 400

    proposals_dir = artifact_dir / "requirement-proposals"
    try:
        proposals_dir.mkdir(mode=0o755, exist_ok=True)
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        base_name = f"{timestamp}-{_proposal_slug(summary)}"
        proposal_path = proposals_dir / f"{base_name}.md"
        counter = 1
        while proposal_path.exists():
            counter += 1
            proposal_path = proposals_dir / f"{base_name}-{counter}.md"
        content = (
            f"# Requirement Proposal — {item_id}\n\n"
            f"## Summary\n\n{summary}\n\n"
            "## Proposed Change\n\n"
            f"{body}\n\n"
            "## Gate Required\n\nrequirements\n"
        )
        proposal_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {"error": f"cannot write proposal: {exc}"}, 500

    return {
        "item_id": item_id,
        "proposal_path": str(proposal_path),
        "gate_required": "requirements",
        "status": "created",
    }, 201


def read_item_artifact(
    board_path: str | Path,
    item_id: str,
    artifact_id: str,
) -> tuple[dict | None, int]:
    item_id = unquote(item_id).strip()
    artifact_id = unquote(artifact_id).strip()
    if not ITEM_ID_RE.match(item_id):
        return {"error": "invalid item id"}, 400
    if artifact_id not in ARTIFACT_FILES:
        return {"error": "artifact not allowed"}, 404

    board_data, error = read_board(board_path)
    if error or board_data is None:
        return {"error": error or "board unavailable"}, 500
    item, _column = _find_board_item(board_data, item_id)
    if item is None:
        return {"error": f"item not found: {item_id}"}, 404

    artifact_dir = _item_artifact_dir(Path(board_path), item_id)
    if artifact_dir is None:
        return {"error": f"item artifacts not found: {item_id}"}, 404

    filename, label = ARTIFACT_FILES[artifact_id]
    artifact_path = artifact_dir / filename
    if not artifact_path.is_file():
        return {"error": f"artifact not found: {artifact_id}"}, 404
    try:
        markdown = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"cannot read artifact: {exc}"}, 500
    return {
        "item_id": item_id,
        "artifact": {
            "id": artifact_id,
            "label": label,
            "filename": filename,
        },
        "markdown": markdown,
    }, 200


def build_item_detail(board_path: str | Path, item_id: str) -> tuple[dict | None, int]:
    item_id = unquote(item_id).strip()
    if not ITEM_ID_RE.match(item_id):
        return {"error": "invalid item id"}, 400

    board_data, error = read_board(board_path)
    if error or board_data is None:
        return {"error": error or "board unavailable"}, 500

    item, column = _find_board_item(board_data, item_id)
    if item is None or column is None:
        return {"error": f"item not found: {item_id}"}, 404

    artifact_dir = _item_artifact_dir(Path(board_path), item_id)
    task_data: dict = {}
    markdown_tasks: list[dict] = []
    warnings: list[str] = []
    pipeline = task_data.get("pipeline", {}) if isinstance(task_data.get("pipeline"), dict) else {}
    if artifact_dir is not None:
        task_yaml, task_error = _read_yaml_file(artifact_dir / "task.yaml")
        if task_yaml is not None:
            task_data = task_yaml
            pipeline = task_data.get("pipeline", {}) if isinstance(task_data.get("pipeline"), dict) else {}
        elif task_error != "not found":
            warnings.append(f"task.yaml: {task_error}")
        default_markdown_status = "done" if column == "done" or pipeline.get("status") == "done" else "unknown"
        markdown_tasks = _tasks_from_markdown(
            artifact_dir / "tasks.md",
            default_status=default_markdown_status,
        )

    yaml_tasks = _tasks_from_task_yaml(task_data)
    tasks, progress_source = _merge_tasks(yaml_tasks, markdown_tasks)
    tasks = _apply_pipeline_task_status(tasks, task_data)
    phase = pipeline.get("current_phase") or column
    gates = task_data.get("gates") if isinstance(task_data.get("gates"), dict) else item.get("gates", {})
    agents = _agents_from_task_data(task_data, item)
    agent_statuses = _agent_statuses_from_task_data(task_data, item, agents)

    return {
        "item": {
            "id": item_id,
            "title": item.get("title", ""),
            "status": item.get("status", ""),
            "column": column,
            "class_of_service": item.get("class_of_service", "Standard"),
        },
        "phase": phase,
        "agents": agents,
        "agent_statuses": agent_statuses,
        "gates": gates or {},
        "tasks": tasks,
        "progress": _progress(tasks, progress_source),
        "evidence": _artifact_evidence(artifact_dir),
        "artifact_path": str(artifact_dir) if artifact_dir is not None else None,
        "warnings": warnings,
    }, 200


# ===== Handler HTTP =====

class CockpitHandler(BaseHTTPRequestHandler):
    """HTTP request handler para o cockpit server."""

    protocol_version = "HTTP/1.1"

    # board_path e html_path são injetados via make_server
    board_path: Path = DEFAULT_BOARD_PATH
    html_path: Path = DEFAULT_HTML_PATH

    def log_message(self, format, *args):  # noqa: A002
        """Suprime logs padrão do http.server para não poluir stdout."""
        pass

    # ------------------------------------------------------------------ #
    #  Roteamento                                                          #
    # ------------------------------------------------------------------ #

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/api/board":
            self._serve_board()
        elif self.path.startswith("/api/item/") and "/artifact/" in self.path:
            if _operations_ui_enabled():
                item_part, artifact_part = self.path[len("/api/item/"):].split("/artifact/", 1)
                self._serve_item_artifact(item_part, artifact_part)
            else:
                self._send_json({"error": "not found"}, status=404)
        elif self.path.startswith("/api/item/"):
            if _operations_ui_enabled():
                item_id = self.path[len("/api/item/"):]
                self._serve_item(item_id)
            else:
                self._send_json({"error": "not found"}, status=404)
        elif self.path == "/api/events":
            self._serve_sse()
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        if (
            self.path.startswith("/api/item/")
            and self.path.endswith("/requirements/proposals")
        ):
            if not _operations_ui_enabled():
                self._send_json({"error": "not found"}, status=404)
                return
            item_id = self.path[len("/api/item/"):-len("/requirements/proposals")]
            self._serve_requirement_proposal(item_id)
        else:
            self._send_json({"error": "not found"}, status=404)

    # ------------------------------------------------------------------ #
    #  GET /                                                               #
    # ------------------------------------------------------------------ #

    def _serve_html(self):
        html_file = self.__class__.html_path
        try:
            content = Path(html_file).read_bytes()
        except OSError:
            # Fallback mínimo se board.html não existir
            content = b"<html><body><h1>cockpit kanban</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # ------------------------------------------------------------------ #
    #  GET /api/board                                                      #
    # ------------------------------------------------------------------ #

    def _serve_board(self):
        data, error = read_board(self.__class__.board_path)
        if error:
            self._send_json({"error": error}, status=500)
            return

        # Atualiza cache
        with _board_cache_lock:
            global _board_cache
            _board_cache = data

        self._send_json(data, status=200)

    # ------------------------------------------------------------------ #
    #  GET /api/item/{id}                                                 #
    # ------------------------------------------------------------------ #

    def _serve_item(self, item_id: str):
        data, status = build_item_detail(self.__class__.board_path, item_id)
        self._send_json(data or {"error": "item detail unavailable"}, status=status)

    def _serve_item_artifact(self, item_id: str, artifact_id: str):
        data, status = read_item_artifact(self.__class__.board_path, item_id, artifact_id)
        self._send_json(data or {"error": "artifact unavailable"}, status=status)

    # ------------------------------------------------------------------ #
    #  POST /api/item/{id}/requirements/proposals                         #
    # ------------------------------------------------------------------ #

    def _serve_requirement_proposal(self, item_id: str):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "invalid content length"}, status=400)
            return
        try:
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"error": "invalid json"}, status=400)
            return
        if not isinstance(payload, dict):
            self._send_json({"error": "json object required"}, status=400)
            return
        data, status = create_requirement_proposal(
            self.__class__.board_path,
            item_id,
            payload,
        )
        self._send_json(data, status=status)

    # ------------------------------------------------------------------ #
    #  GET /api/events (SSE)                                               #
    # ------------------------------------------------------------------ #

    def _serve_sse(self):
        """
        Server-Sent Events endpoint.
        Mantém a conexão aberta e emite eventos quando board.yaml muda.
        Keepalive ": ping\\n\\n" a cada 15s.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Content-Length", str(2_147_483_647))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Cria uma fila de eventos para este cliente
        import queue
        q: queue.Queue = queue.Queue()

        with _subscribers_lock:
            _subscribers.append(q)

        try:
            # Emite estado inicial do board
            with _board_cache_lock:
                cached = _board_cache

            if cached is not None:
                self._write_sse_data(json.dumps(cached))
            else:
                data, _ = read_board(self.__class__.board_path)
                if data is not None:
                    self._write_sse_data(json.dumps(data))
            # Garante bytes suficientes para clientes de teste que usam
            # read(1024) em conexão SSE sem Content-Length.
            self._write_sse_comment("ready " + ("." * 1024))

            # Loop principal: aguarda mensagens ou keepalive
            last_ping = time.time()
            while True:
                try:
                    msg = q.get(timeout=1.0)
                    self._write_sse_data(msg)
                except Exception:
                    pass

                # Keepalive a cada 15s
                if time.time() - last_ping >= 15:
                    self._write_sse_comment("ping")
                    last_ping = time.time()

        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _subscribers_lock:
                try:
                    _subscribers.remove(q)
                except ValueError:
                    pass

    def _write_sse_data(self, json_str: str):
        msg = f"data: {json_str}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

    def _write_sse_comment(self, text: str):
        msg = f": {text}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

    # ------------------------------------------------------------------ #
    #  Helper: enviar JSON                                                 #
    # ------------------------------------------------------------------ #

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ===== File Watcher =====

class BoardWatcher(threading.Thread):
    """
    Thread que monitora board.yaml por mudanças via poll de mtime.
    Intervalo: 800ms.
    Quando detecta mudança: parseia e broadcast para todos os SSE subscribers.
    Se YAML inválido: usa cache da última versão válida.
    """

    def __init__(self, board_path: Path, poll_interval: float = 0.8):
        super().__init__(daemon=True, name="cockpit-watcher")
        self.board_path = Path(board_path)
        self.poll_interval = poll_interval
        self._last_mtime: float | None = None

    def run(self):
        while True:
            try:
                self._check()
            except Exception as exc:
                pass  # Nunca crasha o watcher
            time.sleep(self.poll_interval)

    def _check(self):
        global _board_cache

        try:
            mtime = self.board_path.stat().st_mtime
        except OSError:
            return

        if self._last_mtime is None:
            self._last_mtime = mtime
            # Carrega versão inicial no cache
            data, _ = read_board(self.board_path)
            if data is not None:
                with _board_cache_lock:
                    _board_cache = data
            return

        if mtime != self._last_mtime:
            self._last_mtime = mtime
            data, error = read_board(self.board_path)

            if error:
                print(f"[cockpit-watcher] Erro ao ler board.yaml: {error}. Usando cache.", file=sys.stderr)
                # Usa cache da última versão válida
                with _board_cache_lock:
                    data = _board_cache
            else:
                with _board_cache_lock:
                    _board_cache = data

            if data is None:
                return

            # Broadcast para todos os subscribers SSE
            payload = json.dumps(data)
            with _subscribers_lock:
                dead = []
                for q in _subscribers:
                    try:
                        q.put_nowait(payload)
                    except Exception:
                        dead.append(q)
                for q in dead:
                    _subscribers.remove(q)


# ===== Factory =====

def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    board_path: str | Path = DEFAULT_BOARD_PATH,
    html_path: str | Path = DEFAULT_HTML_PATH,
) -> ThreadingHTTPServer:
    """
    Cria e retorna um HTTPServer configurado para o cockpit.
    Não inicia o watcher (caller deve iniciar se quiser SSE).
    """
    board_path = Path(board_path)
    html_path = Path(html_path)

    # Cria classe handler personalizada com caminhos injetados
    handler_class = type(
        "BoundCockpitHandler",
        (CockpitHandler,),
        {
            "board_path": board_path,
            "html_path": html_path,
        },
    )

    class ReusableHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = ReusableHTTPServer((host, port), handler_class)
    return server


# ===== Entrypoint =====

def main():
    """Ponto de entrada do servidor como daemon."""
    # Feature flag: COCKPIT_ENABLED (default: roda normalmente se não definida)
    enabled_env = os.environ.get("COCKPIT_ENABLED", "").strip().lower()
    if enabled_env in ("false", "0", "no"):
        print("[cockpit] COCKPIT_ENABLED=false — servidor não iniciado.", file=sys.stderr)
        sys.exit(0)

    if not YAML_AVAILABLE:
        print(
            "[cockpit] AVISO: PyYAML não disponível.\n"
            "         Usando parser YAML mínimo embutido.",
            file=sys.stderr,
        )

    port = int(os.environ.get("COCKPIT_PORT", DEFAULT_PORT))
    host = DEFAULT_HOST
    board_path = DEFAULT_BOARD_PATH
    html_path = DEFAULT_HTML_PATH

    server = make_server(host=host, port=port, board_path=board_path, html_path=html_path)

    # Inicia file watcher
    watcher = BoardWatcher(board_path)
    watcher.start()

    print(f"[cockpit] Servidor iniciado em http://{host}:{port}", file=sys.stderr)
    print(f"[cockpit] Board: {board_path}", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[cockpit] Encerrando...", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
