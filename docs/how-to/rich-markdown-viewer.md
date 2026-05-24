# Rich Markdown no Cockpit

Rich markdown está **ativado por padrão** após `./setup.sh --all`. Não é necessário exportar variável de ambiente.

## Comportamento padrão

Após instalação, o cockpit serve:

- `GET /api/config` → `{ "rich_markdown_enabled": true, ... }`
- `GET /markdown-renderer.js` → parser UMD com Mermaid, tabelas e sanitização

Basta iniciar o cockpit (via skill ou `python3 ~/.kanban-cortex-harness-agents/cockpit/check.py`).

## Desativar (rollback)

Para voltar ao renderer legado:

```bash
export COCKPIT_RICH_MARKDOWN_ENABLED=false
python3 ~/.kanban-cortex-harness-agents/cockpit/server.py
```

## Suportado (rich mode)

- Tabelas Markdown
- Diagramas Mermaid (` ```mermaid `)
- Listas aninhadas, blockquotes, links
- Sanitização allowlist (sem scripts)

## Artefatos

- `src/cockpit/markdown-renderer.js` — parser e sanitize
- `src/cockpit/board.html` — popup integrado
- `setup.sh` — copia renderer para `~/.kanban-cortex-harness-agents/cockpit/`
