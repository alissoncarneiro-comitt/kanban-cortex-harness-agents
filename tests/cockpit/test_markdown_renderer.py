"""Tests for cockpit markdown renderer (FEAT-014)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "src" / "cockpit" / "markdown-renderer.js"
SERVER = ROOT / "scripts" / "cockpit" / "server.py"


def _run_node(script: str) -> dict:
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout.strip())


@pytest.fixture(scope="module")
def md():
    renderer_path = RENDERER.as_posix()
    return _run_node(
        f"""
        const m = require('{renderer_path}');
        const rich = (text) => m.renderMarkdown(text, {{ rich: true }});
        const legacy = (text) => m.renderMarkdown(text, {{ rich: false }});
        console.log(JSON.stringify({{
          table: rich('| A | B |\\n|---|---|\\n| 1 | 2 |'),
          mermaid: rich('```mermaid\\ngraph TD; A-->B;\\n```'),
          xss: rich('<script>alert(1)</script>\\n\\n**ok**'),
          legacyHeading: legacy('# Title'),
        }}));
        """
    )


def test_renderer_file_exists():
    assert RENDERER.is_file()


def test_table_renders_html_table(md):
    html = md["table"]
    assert "<table>" in html
    assert "<th>" in html
    assert "<td>" in html


def test_mermaid_block_renders_container(md):
    html = md["mermaid"]
    assert 'class="mermaid"' in html
    assert "graph TD" in html
    assert "<pre><code>" not in html


def test_xss_stripped_in_server_mode(md):
    html = md["xss"]
    assert "<script" not in html.lower()
    assert "<strong>ok</strong>" in html


def test_legacy_mode_unchanged(md):
    assert "<h1>Title</h1>" in md["legacyHeading"]


def test_build_cockpit_config_default():
    code = """
import importlib.util
spec = importlib.util.spec_from_file_location('srv', r'%s')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.build_cockpit_config()['rich_markdown_enabled'])
""" % SERVER.as_posix()
    result = subprocess.run(
        ["python3", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
        env={k: v for k, v in __import__("os").environ.items() if k != "COCKPIT_RICH_MARKDOWN_ENABLED"},
    )
    assert result.stdout.strip() == "True"


def test_build_cockpit_config_opt_out():
    code = """
import importlib.util
spec = importlib.util.spec_from_file_location('srv', r'%s')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.build_cockpit_config()['rich_markdown_enabled'])
""" % SERVER.as_posix()
    env = {**__import__("os").environ, "COCKPIT_RICH_MARKDOWN_ENABLED": "false"}
    result = subprocess.run(
        ["python3", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
        env=env,
    )
    assert result.stdout.strip() == "False"
