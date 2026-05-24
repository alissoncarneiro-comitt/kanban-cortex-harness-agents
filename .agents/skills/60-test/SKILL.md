---
name: a-test
description: >-
  Agent Harness QA — E2E browser, OWASP/STRIDE, Lighthouse, regression tests.
  Use when user invokes /a-test or /a-qa after review.
aliases: ["/a-test", "/a-qa"]
triggers: ["user", "model"]
---

# Test — QA, Segurança e Performance

> **Papel**: QA Lead + Security Officer + Performance Engineer.
> **Referências**: cc-sdd `kiro-validate-impl` | gstack `/qa`, `/cso`, `/benchmark` | Kanban coluna Test (WIP=3)

## Contexto de Entrada

> **ISOLAMENTO OBRIGATÓRIO**: Esta fase deve rodar em uma sessão Nova do agente.
> Não acesse nem infira informações do histórico de conversas anteriores.
> **O QA valida contra os ACs originais — não contra o que o reviewer aprovou.**

### Artefatos obrigatórios — ler NESTA ORDEM
1. `.agents/kanban/in-progress/{ITEM}/requirements.md` (status: APPROVED) — derive todos os casos de teste dos ACs Given-When-Then
2. Código no estado atual do branch `feature/{ITEM}` — o que foi efetivamente implementado

### Artefatos proibidos
- Histórico de conversa desta ou de sessões anteriores
- `review-report.md` — **não leia antes de executar os testes**; o QA não deve ser influenciado pelo que o reviewer encontrou ou aprovou
- `design.md`, `brief.md` — o QA valida comportamento, não arquitetura
- `Implementation Notes` — o QA não precisa saber como foi implementado, apenas se funciona

### Protocolo de independência
**Antes de executar qualquer teste:**
1. Leia todos os ACs de `requirements.md`
2. Para cada AC, escreva o caso de teste correspondente (Given-When-Then → test case)
3. Execute os testes derivados dos ACs
**Depois de executar:**
4. Verifique cobertura, segurança, performance
5. Somente então leia `review-report.md` para verificar se o reviewer encontrou algo que você não testou

### Validação de pré-requisitos
Se `requirements.md` não tiver status APPROVED ou não houver branch `feature/{ITEM}`:
→ Interromper: "Review não aprovado. Execute `/a-review {ITEM}` e aguarde aprovação."

### Handoff de entrada
`a-review` → este skill via review aprovado (`review-report.md` com status APPROVE) + código em `feature/{ITEM}`

## Pré-requisitos

- Review aprovado
- Acceptance criteria de `requirements.md` disponíveis

## Workflow

### 1. E2E (browser real)

```bash
python .agents/skills/60-test/scripts/e2e-runner.py --feature {ITEM}
```

- Fluxos Given-When-Then
- Screenshots before/after
- Bug → regression test → re-verify

### 2. Security

```bash
python .agents/skills/60-test/scripts/security-scan.py --target src/
```

- OWASP Top 10 + STRIDE
- Gate: confidence ≥ 8/10

### 3. Performance

```bash
python .agents/skills/60-test/scripts/perf-benchmark.py --baseline perf-baseline.json
```

- Core Web Vitals, P95 latency
- Regressão > 20% = bloqueio

### 4. Coverage Gate

```bash
python .agents/skills/60-test/scripts/coverage-gate.py --min 0.60
```

### 5. Regression

```bash
python .agents/skills/60-test/scripts/regression-gen.py --bug-id {ID}
```

## Regras de Ouro

- NUNCA ship sem QA verde
- SEMPRE regression test por bug encontrado
- NUNCA ignore performance regression > 20%

## Entrada / Saída

| Entrada | Saída |
|---------|-------|
| Código reviewado | `qa-report.md`, `security-report.md`, regression tests |

**Paths**: `.agents/kanban/in-progress/{ITEM}/qa-report.md`

## Instrumentação

> Emite eventos de audit trail para `scripts/audit_writer.py` (FEAT-002).
> Variáveis de ambiente capturadas automaticamente pelo harness se disponíveis.

### Ao iniciar este skill (phase_start)

```bash
python3 scripts/cockpit/check.py 2>/dev/null || python scripts/cockpit/check.py 2>/dev/null || true

python scripts/audit_writer.py phase_start \
  --item {ITEM_ID} \
  --phase {PHASE} \
  --model "${CLAUDE_MODEL_ID:-unknown}" \
  --session "${CLAUDE_SESSION_ID:-$(python3 -c "import uuid; print(uuid.uuid4())")}" \
  --tokens-input "${CLAUDE_INPUT_TOKENS:-}" \
  --context-pct "${CLAUDE_CONTEXT_PCT:-}"
```

### Ao finalizar este skill (phase_end)

```bash
python scripts/audit_writer.py phase_end \
  --item {ITEM_ID} \
  --phase {PHASE} \
  --model "${CLAUDE_MODEL_ID:-unknown}" \
  --session "${CLAUDE_SESSION_ID:-}" \
  --tokens-input "${CLAUDE_INPUT_TOKENS:-}" \
  --tokens-output "${CLAUDE_OUTPUT_TOKENS:-}" \
  --tokens-cache-read "${CLAUDE_CACHE_READ_TOKENS:-}" \
  --tokens-cache-write "${CLAUDE_CACHE_WRITE_TOKENS:-}" \
  --context-pct "${CLAUDE_CONTEXT_PCT:-}" \
  --status {done|blocked|rejected} \
  --artifacts "{artifacts produzidos}"
```

> Fallback: se `scripts/audit_writer.py` ausente, prosseguir sem interromper o skill.

## Handoff para Pipeline

Ao finalizar QA verde:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase test --status passed
```

Ao finalizar QA com falha:

```bash
python scripts/orchestrator/handoff.py --item {ITEM} --phase test --status failed
```

Cada chamada a `handoff.py` atualiza `handoff-packet.yaml` para a transição seguinte. Schema: `docs/reference/handoff-packet-schema.md`. Em test, `review-report.md` não deve constar em `artifacts_allowed` até após os testes próprios.
