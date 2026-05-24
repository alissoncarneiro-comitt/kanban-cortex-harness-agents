# Template — Bloco `## Contexto de Entrada`

> Copie e adapte este bloco para o topo de cada SKILL.md, logo após o frontmatter YAML
> e antes de qualquer seção `## Workflow` ou `## Modos de Operação`.
> Substitua os placeholders `<...>` pelos valores específicos do skill.

---

```markdown
## Cockpit (Kanban Board)

> Antes de qualquer ação, verifique silenciosamente se o Cockpit está ativo.
> Se não estiver, inicie-o em background — falhas são ignoradas (o board é opcional).

```bash
python3 ~/.kanban-cortex-harness-agents/cockpit/check.py
```

O board estará disponível em http://127.0.0.1:8337 enquanto você trabalha.

---

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> Leia apenas os artefatos listados abaixo antes de qualquer ação.

### Artefatos obrigatórios
- `.agents/steering/product.md`
- `.agents/steering/tech.md`
- `.agents/steering/conventions.md`
- `<path do artefato de entrada específico desta fase>` — ex: `brief.md`, `requirements.md`, `design.md`

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `<artefatos produzidos por fases anteriores não listados acima>` — ex: `review-report.md` para a-test

### Validação de pré-requisitos
Se o artefato obrigatório não existir ou não estiver com status `APPROVED`/`LOCKED`:
→ Interromper e exibir: "Artefato `<path>` ausente ou não aprovado. Execute `scripts/launch-phase.sh {ITEM} <fase-anterior>` primeiro."

### Handoff de entrada
`<fase anterior>` → este skill via `<artefato>` aprovado em `<path>`
```

---

## Guia de preenchimento por skill

| Skill | Artefato obrigatório adicional | Artefatos proibidos adicionais |
|-------|-------------------------------|-------------------------------|
| `a-steering` | nenhum | nenhum |
| `a-discover` | nenhum | qualquer spec/, design.md |
| `a-po` | `raw-request.md` | histórico de sessão |
| `a-spec` | `brief.md` (APPROVED) | histórico de discover, brief de outras features |
| `a-design` | `requirements.md` (APPROVED) + `design.md` (LOCKED) | histórico de po/spec |
| `a-build` | `design.md` (LOCKED) + `tasks.md` (APPROVED) | histórico de design/spec |
| `a-review` | `design.md` (LOCKED) + `tasks.md` + diff de código | `Implementation Notes` do builder, histórico de build |
| `a-test` | `requirements.md` (ACs) + código commitado | `review-report.md`, histórico de review |
| `a-ship` | `qa-report.md` (verde) | histórico de build/review/test |
| `a-flow` | `board.yaml` + `daily-logs/` (últimos 2) | histórico de cerimônias anteriores |
| `a-reflect` | `board.yaml` + `done/` (últimos 5) + `reviews/` | histórico de reflect anterior |
| `a-replenish` | `board.yaml` + `backlog/` (WSJF ordenado) | histórico de replenish anterior |
