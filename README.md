# Agent Harness Engineering Kanban

> **Spec-Driven + Role-Based + Kanban-Flow** para Agent Swarms de Engenharia.
> Inspirado em [cc-sdd](https://github.com/gotalab/cc-sdd), [gstack](https://github.com/garrytan/gstack) e Kanban Ágil.

## Filosofia

**Menos é mais.** 7 papéis, 3 cerimônias, 6 artefatos. Cada papel é um skill independente. Cada artefato é um contrato. O Kanban é o sistema nervoso que orquestra tudo.

> "Specs are contracts between parts of the system, not master commands."
> "Agents write the spec, humans approve the contract, code is what ships."

## Estrutura em 30 segundos

```
.agents/                  ← Cérebro do swarm (CANÔNICO)
├── skills/
│   ├── 00-steering/      ← Bootstrap, routing, gates (Fase 0)
│   ├── 10-discovery/     ← CEO + PO (Discover + Priorize)
│   ├── 15-po/            ← PO fast-track (prompt → requirements → design → tasks)
│   ├── 20-spec/          ← Tech Lead + System Design (EARS + Lock)
│   ├── 30-design/        ← UI/UX + Design Engineer
│   ├── 40-build/         ← Implementação TDD (RED→GREEN)
│   ├── 50-review/        ← Staff Eng + Cross-Model Review
│   ├── 60-test/          ← QA + Security + Performance
│   ├── 70-ship/          ← Release + SRE + Docs
│   └── 80-governance/    ← Replenish + Flow + Reflect + Plan
├── steering/             ← Memória persistente (cc-sdd style)
├── kanban/               ← WIP limits, colunas, políticas
└── AGENTS.md             ← Constituição (na raiz do repo)
kanban/                   ← Symlink → .agents/kanban/
templates/                ← Artefatos-padrão
```

## Os Papéis

| # | Papel | Skill | O que faz | Quando chamar |
|---|-------|-------|-----------|---------------|
| 0 | **Steering** | `/a-steering` | Bootstrap, routing, gates de aprovação | Projeto novo ou decisão estratégica |
| 1a | **Discovery** | `/a-discover` | Reframe, brief, WSJF (modo estudo) | Escopo vago — ainda estamos explorando |
| 1b | **PO** | `/a-po "prompt"` | Requirements → design → tasks com gates | Escopo claro — já sabemos o que quer |
| 2 | **Spec** | `/a-spec` | Requirements EARS, design.md (locked), tasks.md | Após brief aprovado |
| 3 | **Designer** | `/a-design` | Design system, mockups, HTML/CSS/JS | Quando há UI |
| 4 | **Engineer** | `/a-build` | TDD RED→GREEN, 1 task/iteração, feature flags | Após design locked |
| 5 | **Reviewer** | `/a-review` | Failure modes, boundary violations | Após build |
| 6 | **QA** | `/a-test` | Browser real, E2E, OWASP, performance | Após review |
| 7 | **Shipper** | `/a-ship` | PR, CI, deploy, docs, canary | Após QA verde |
| 8 | **Governance** | `/a-replenish`, `/a-flow`, `/a-reflect` | Cerimônias Kanban + `/a-plan` | Operacional contínuo |

## As 3 Cerimônias Kanban

| Cerimônia | Skill | Frequência | Propósito |
|-----------|-------|------------|-----------|
| **Replenish** | `/a-replenish` | On-demand (backlog vazio ou slots livres) | Puxar do backlog respeitando WIP limits |
| **Flow** | `/a-flow` | Diária ou quando item parado > 4h | Detectar gargalos, redistribuir carga |
| **Reflect** | `/a-reflect` | Quinzenal ou a cada 5 itens concluídos | Lead Time, Throughput, ações de melhoria |

## Os 6 Artefatos (Contratos)

1. **`brief.md`** — Saída do `/a-discover`. O que, para quem, por quê.
2. **`requirements.md`** — EARS format (via `/a-po` ou `/a-spec`).
3. **`design.md`** — **LOCKED** após approve. Arquitetura, data flow, File Structure Plan.
4. **`tasks.md`** — Tasks com `_Boundary:_` e `_Depends:_`. Guia o `/a-build`.
5. **`qa-report.md`** — Resultados de testes, bugs, regressões, security scan.
6. **`ship-log.md`** — PR, deploy verificado, docs atualizadas, métricas.

## Fluxo de Trabalho (1 Feature End-to-End)

### Caminho A — Escopo claro (`/a-po`)

```
[Human] /a-po "Quero pagamentos com PIX"
    │
    ▼
requirements.md ──► /a-steering approve requirements
    │
    ▼
design.md (LOCKED) ──► /a-steering approve design
    │
    ▼
tasks.md ──► /a-steering approve tasks
    │
    ▼
/a-design (se UI) → /a-build → /a-review → /a-test → /a-ship
```

### Caminho B — Escopo vago (`/a-discover`)

```
[Human] "Quero explorar pagamentos com PIX"
    │
    ▼
/a-discover ──► brief.md + stakeholder-map + acceptance-criteria
    │
    ▼
/a-steering approve brief
    │
    ▼
/a-spec ──► requirements.md (EARS) + design.md (LOCKED) + tasks.md
    │
    ▼
/a-design ──► DESIGN.md + mockups (se houver UI)
    │
    ▼
/a-build ──► TDD por task (RED→GREEN), feature flag
    │
    ▼
/a-review → /a-test → /a-steering approve ship → /a-ship → /a-reflect
```

## Regras de Ouro

1. **Design Locked**: `design.md` é imutável após approve. Mudança = novo ciclo.
2. **Boundary First**: Cada task tem `_Boundary:_` claro. Reviewer verifica violações.
3. **1 Task por Iteração**: Engineer faz 1 task, commita, reviewer verifica, próxima task.
4. **WIP Limit**: Máximo 3 itens por agente, 10 total no swarm.
5. **Safety First**: `/careful` (destructive ops), `/freeze` (scope lock), `/guard` (both).
6. **Code is Truth**: Specs guiam, mas código é a fonte da verdade.
7. **No Heroics**: Item parado > 8h é bloqueado. Daily Flow redistribui.
8. **Isolamento de Contexto**: Cada fase roda em sessão nova. Artefatos aprovados são o único canal entre fases. Use `scripts/launch-phase.sh` para iniciar cada fase. → [Por que isso importa](docs/explanation/context-isolation.md)

## Instalação

```bash
# 1. Clone ou copie o framework no seu projeto
git clone https://github.com/seu-org/agent-harness-engineering-kanban.git .

# 2. Instale skills para seu agente
./setup.sh --claude   # /a-* no Claude Code
./setup.sh --codex    # $a-* no Codex CLI (ver docs/how-to/codex-cli.md)
./setup.sh --all      # todas as plataformas

# 3. Bootstrap do projeto (obrigatório)
#    Abra NOVA sessão Claude e confira /help
/a-steering init

# 4. Escolha o caminho de entrada
/a-po "implementar pagamentos PIX"   # escopo claro
# ou
/a-discover "explorar pagamentos PIX"  # escopo vago
```

Multi-plataforma: [`docs/reference/agent-adapters.md`](docs/reference/agent-adapters.md)

## Comandos Rápidos

```bash
/a-steering init                      # Bootstrap: AGENTS.md + steering docs
/a-steering route                     # Próximo comando recomendado
/a-po "prompt claro"                  # Fast-track: requirements → design → tasks
/a-discover "ideia vaga"              # Modo estudo: brief.md
/a-steering approve requirements|brief|design|tasks  # Human gates
/a-spec                               # Spec após brief (caminho discover)
/a-design                             # UI/UX (se aplicável)
/a-build                              # TDD, 1 task/iteração
/a-review                             # Boundary check + failure modes
/a-test                               # E2E + security + perf
/a-steering approve ship              # Human gate
/a-ship                               # PR → deploy → docs
/a-replenish / /a-flow / /a-reflect   # Cerimônias Kanban
```

## Board Online

O cookip sobe automaticamente no início dos skills via `scripts/cookip/check.py`.
Para abrir manualmente:

```bash
python3 scripts/cookip/check.py
```

Depois acesse `http://127.0.0.1:8337`. Use `COOKIP_PORT` para trocar a porta.

## Licença

MIT. Fork e adapte para sua empresa.
