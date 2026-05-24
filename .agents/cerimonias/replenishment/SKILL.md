---
name: replenish
aliases: ["/a-replenish", "/a-refill"]
description: >-
  Cerimônia: Reunião de Reabastecimento (Replenishment Meeting).
  Use quando: o quadro Kanban tem slots livres ou o backlog precisa de priorização.
  Puxa itens do backlog para a coluna "Ready" respeitando WIP limits e capacidade.
  NUNCA excede WIP limits. NUNCA puxa sem capacidade disponível.

# Replenishment — Reabastecendo o Quadro

## Responsabilidades
1. Verificar capacidade atual (WIP total e por agente)
2. Priorizar backlog usando WSJF (Weighted Shortest Job First)
3. Puxar itens respeitando classes de serviço
4. Criar task.yaml para cada item puxado
5. Registrar decisões em replenishment-log.md

## Workflow

### 1. Capacity Check
```bash
python .agents/cerimonias/replenishment/scripts/capacity-planner.py
```
- WIP total: X/10
- Slots livres: Y
- Se Y == 0: ABORTAR (não puxar nada)

### 2. Priorização
```bash
python .agents/cerimonias/replenishment/scripts/wsjf-prioritizer.py
```
- Lê `kanban/backlog/*/business-case.md`
- Calcula WSJF = (Business Value + Risk Reduction + Time Criticality) / Job Size
- Ordena por score decrescente

### 3. Seleção
Para cada slot livre:
- Pegar próximo item do ranking
- Verificar classe de serviço:
  - 🟢 Standard: conta 1 no WIP
  - 🟡 Expedite: conta 2 no WIP, máximo 2 simultâneos
  - 🔴 Fixed Date: prioridade automática, deadline rígida
- Verificar dependências externas (ex: precisa de API de terceiro?)
- Mover diretório de `backlog/` para `in-progress/`
- Criar `task.yaml` com owner, reviewer, tester, fases

### 4. Registro
```markdown
# Replenishment Log — 2026-05-23

**Slots Livres**: 3
**Itens Puxados**: 2

1. FEATURE-042 (Score: 8.4) — Standard — Owner: agent-2
2. FEATURE-038 (Score: 6.2) — Standard — Owner: agent-3

**Itens Rejeitados**: 1
- FEATURE-051: WIP limit de Expedite atingido, aguardar

**Próximo Replenishment**: quando WIP cair < 7
```

## Regras de Ouro
- NUNCA exceda WIP total (10) ou por agente (3)
- SEMPRE respeite classes de serviço
- NUNCA puxe item sem business-case.md
- SEMPRE aloque reviewer independente do owner
