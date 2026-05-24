---
name: daily
aliases: ["/a-daily", "/a-flow-check"]
description: >-
  Cerimônia: Reunião de Fluxo de Trabalho (Daily Kanban).
  Use quando: check-in diário ou quando um item está parado há > 4h.
  Avalia gargalos, remove impedimentos, redistribui carga entre agents.
  NUNCA deixe um item em "In Progress" sem atividade por > 8h.

# Daily Flow — Check-in Diário do Swarm

## Responsabilidades
1. Detectar itens parados (> 4h alert, > 8h blocked)
2. Identificar gargalos (acúmulo em Review/Test)
3. Redistribuir carga (agente sobrecarregado → agente ocioso)
4. Escalar impedimentos para Steering quando necessário
5. Registrar tudo em daily-log-YYYY-MM-DD.md

## Workflow

### 1. Scan
```bash
python .agents/cerimonias/daily-flow/scripts/bottleneck-detector.py
```

### 2. Review por Item
Para cada item alertado ou bloqueado:
- Ler `task.yaml` — identificar owner e fase atual
- Verificar último commit/artefato (git log ou mtime)
- Decidir:
  - **Continuar**: owner mantém, mas com prazo de resolução
  - **Escalar**: transferir para agente mais senior ou humano
  - **Devolver**: voltar para "Ready" se bloqueio externo
  - **Split**: quebrar item em partes menores

### 3. Rebalanceamento
- Se agente tem 0 itens → puxar do backlog (trigger replenishment)
- Se agente tem > 3 itens → transferir 1 para agente com capacidade
- Se fase "Review" tem > 4 itens → adicionar reviewer ou paralelizar
- Se fase "Test" tem > 4 itens → adicionar QA ou automatizar mais

### 4. Ações
```markdown
# Daily Flow — 2026-05-23

## Itens Alerta (> 4h idle)
- FEATURE-015 (Build) | Owner: agent-3 | 5.2h idle → **Action**: Verificar com agent-3

## Itens Bloqueados (> 8h idle)
- FEATURE-022 (Review) | Owner: agent-4 | 9.1h idle → **Action**: Transferir para agent-1

## Gargalos Detectados
- Fase "Test": 4/4 itens → **Action**: Escalar para Steering (precisamos de mais QA?)

## Rebalanceamento
- FEATURE-030 transferido de agent-2 (3 itens) → agent-5 (1 item)

## Próximo Daily
- Amanhã 09:00 ou se novo blocked surgir
```

## Regras de Ouro
- NUNCA ignore um blocked
- SEMPRE tente resolver internamente antes de escalar
- SEMPRE documente ação tomada
- NUNCA deixe agente ocioso se há trabalho no backlog
