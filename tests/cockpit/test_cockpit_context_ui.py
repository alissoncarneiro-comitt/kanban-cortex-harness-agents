"""Tests for cockpit project/context UI wiring."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "src" / "cockpit" / "board.html"


def _run_board_script(body: str, search: str = "") -> dict:
    script = textwrap.dedent(
        """
        const fs = require('fs');

        const html = fs.readFileSync(__BOARD_PATH__, 'utf8');
        const start = html.lastIndexOf('<script>');
        const end = html.lastIndexOf('</script>');
        const inline = html.slice(start + '<script>'.length, end);

        const elements = Object.create(null);
        function makeElement(tag, id) {
          return {
            id: id || '',
            tagName: String(tag || 'div').toUpperCase(),
            children: [],
            style: {},
            className: '',
            innerHTML: '',
            textContent: '',
            value: '',
            disabled: false,
            title: '',
            dataset: {},
            attributes: {},
            addEventListener() {},
            appendChild(child) {
              this.children.push(child);
              return child;
            },
            setAttribute(name, value) {
              this.attributes[name] = String(value);
              this[name] = value;
            },
            getAttribute(name) {
              return this.attributes[name];
            },
            querySelector() {
              return null;
            },
            querySelectorAll() {
              return [];
            },
            remove() {},
            focus() {},
            scrollBy() {},
          };
        }
        function getElementById(id) {
          if (!elements[id]) {
            elements[id] = makeElement('div', id);
          }
          return elements[id];
        }

        global.URL = URL;
        global.URLSearchParams = URLSearchParams;
        global.window = {
          __COCKPIT_TEST_MODE: true,
          location: {
            search: __SEARCH__,
            href: 'http://127.0.0.1:8337/' + (__SEARCH__ ? __SEARCH__ : ''),
          },
          history: {
            replaceState(_a, _b, url) {
              window.__replacedUrl = url;
            },
          },
          localStorage: {
            _data: Object.create(null),
            getItem(key) {
              return Object.prototype.hasOwnProperty.call(this._data, key) ? this._data[key] : null;
            },
            setItem(key, value) {
              this._data[key] = String(value);
            },
          },
        };
        global.document = {
          getElementById,
          createElement(tag) {
            return makeElement(tag);
          },
          querySelectorAll() {
            return [];
          },
          addEventListener() {},
        };
        global.fetch = async () => ({ ok: true, json: async () => ({}) });
        global.EventSource = function EventSource() {
          this.close = () => {};
        };
        global.console = { log() {}, warn() {}, error() {} };

        const userBody = __BODY__;
        const run = new Function(
          'window',
          'document',
          'fetch',
          'EventSource',
          'URL',
          'URLSearchParams',
          'console',
          inline + String.fromCharCode(10) + userBody
        );
        const result = run(window, document, fetch, EventSource, URL, URLSearchParams, console);
        process.stdout.write(JSON.stringify(result));
        """
    ).replace("__BOARD_PATH__", json.dumps(str(BOARD))).replace("__SEARCH__", json.dumps(search))
    script = script.replace("__BODY__", json.dumps(body))

    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout.strip())


def test_board_html_exposes_context_controls() -> None:
    html = BOARD.read_text(encoding="utf-8")

    assert 'id="project-selector"' in html
    assert 'id="source-selector"' in html
    assert 'id="context-badge"' in html
    assert 'aria-label="Seletor de projeto e origem"' in html


def test_context_helpers_prefer_url_and_build_query_urls() -> None:
    payload = _run_board_script(
        """
        projectCatalog = [
          { project_id: 'alpha', name: 'Alpha', source_mode: 'project', active: false },
          { project_id: 'beta', name: 'Beta', source_mode: 'hub', active: true },
        ];
        window.localStorage.setItem(CONTEXT_STORAGE_KEY, JSON.stringify({
          project_id: 'beta',
          source: 'project',
        }));
        cockpitConfig.project_hub_enabled = true;
        const initial = resolveInitialContext();
        return {
          initial,
          board: buildBoardUrl(initial),
          events: buildEventsUrl(initial),
          item: buildItemUrl('FEAT-9', initial),
          artifact: buildArtifactUrl('FEAT-9', 'brief', initial),
        };
        """,
        search='?project_id=alpha&source=hub',
    )

    assert payload["initial"] == {"project_id": "alpha", "source": "hub"}
    assert payload["board"] == "/api/board?project_id=alpha&source=hub"
    assert payload["events"] == "/api/events?project_id=alpha&source=hub"
    assert payload["item"] == "/api/item/FEAT-9?project_id=alpha&source=hub"
    assert payload["artifact"] == "/api/item/FEAT-9/artifact/brief?project_id=alpha&source=hub"


def test_context_helpers_persist_and_hide_single_project_fallback() -> None:
    payload = _run_board_script(
        """
        cockpitConfig.project_hub_enabled = false;
        projectCatalog = [];
        persistContext({ project_id: 'alpha', source: 'project' });
        const stored = readContextFromStorage();
        syncProjectControls();
        const panel = document.getElementById('project-context');
        const selector = document.getElementById('project-selector');
        return {
          stored,
          panelDisplay: panel.style.display,
          selectorDisabled: selector.disabled,
          boardUrl: buildBoardUrl({ project_id: 'alpha', source: 'project' }),
        };
        """
    )

    assert payload["stored"] == {"project_id": "alpha", "source": "project"}
    assert payload["panelDisplay"] == "none"
    assert payload["selectorDisabled"] is True
    assert payload["boardUrl"] == "/api/board"
