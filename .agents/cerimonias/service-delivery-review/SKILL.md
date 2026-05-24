---
name: review-service
aliases: ["/a-sdr", "/a-flow-review"]
description: >-
  Cerimônia: Revisão de Serviço (Service Delivery Review).
  Use quando: quinzenal/mensal ou após N itens completados.
  Avalia métricas do Kanban (Lead Time, Throughput, Cycle Time) e propõe melhorias.
  NUNCA ignore métricas que indicam degradação do fluxo.

# Service Delivery Review — Avaliando a Saúde do Fluxo

## Responsabilidades
1. Coletar métricas de `kanban/done/`
2. Calcular Lead Time, Cycle Time, Throughput
3. Gerar CFD (Cumulative Flow Diagram)
4. Identificar tendências e anomalias
5. Propor ajustes (WIP limits, skills, processo)
6. Registrar action items

## Workflow

### 1. Coleta de Métricas
```bash
python .agents/cerimonias/service-delivery-review/scripts/metrics-collector.py
```

### 2. Análise
Para o período analisado:
- **Throughput**: Itens completados / semana
- **Lead Time**: Média e mediana (Backlog → Done)
- **Cycle Time**: Média e mediana (Build → Done)
- **Flow Efficiency**: % de tempo ativo vs. esperando
- **WIP Aging**: Tempo médio em cada coluna

### 3. Identificação de Padrões
- Lead Time crescente → WIP limit muito alto ou gargalo em Review/Test
- Throughput baixo → itens muito grandes (quebrar em menores)
- Muitos itens em Build → necessidade de mais agents ou melhor planning
- Review pendente > 2h → reviewers insuficientes ou items muito complexos
- Test falhando > 1h → qualidade de build ou ambiente de teste instável

### 4. Propostas de Melhoria
- Ajustar WIP limits (aumentar ou reduzir)
- Adicionar/remover skills especializadas
- Ajustar thresholds do bottleneck detector
- Melhorar test automation (reduzir tempo em Test)
- Parallelizar Review (múltiplos reviewers por item)

### 5. Registro
```markdown
# Service Delivery Review — Maio 2026

## Métricas
| Métrica | Valor | Meta | Status |
|---------|-------|------|--------|
| Throughput | 14 itens/semana | 7 | ✅ +100% |
| Avg Lead Time | 68h | < 72h | ✅ |
| Avg Cycle Time | 45h | < 48h | ✅ |
| Flow Efficiency | 42% | > 40% | ✅ |

## Tendências
- Lead Time cresceu 15% na última semana → possível gargalo em Test

## Action Items
1. [ ] Reduzir threshold de review de 2h para 1h
2. [ ] Adicionar skill de teste paralelo (sharded QA)
3. [ ] Quebrar itens > 3 dias de estimativa
4. [ ] Revisar WIP limit de Test (atual: 4, proposto: 5)

## Próxima Review
- 2026-06-15
```

## Regras de Ouro
- NUNCA ignore Lead Time crescente
- SEMPRE proponha ação concreta (não apenas observe)
- SEMPRE compare contra metas definidas em board.yaml
- NUNCA deixe action items sem owner e deadline
