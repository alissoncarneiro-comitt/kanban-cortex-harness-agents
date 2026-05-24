# Steering — Conventions

> Gerado por `/a-steering init`. Regras que todos os agentes devem seguir.

## Commits

```
[FEATURE-XXX] <tipo>: descrição

[harness-context]
- Decisão: [o que foi decidido]
- Próximo: [o que falta]
- Bloqueio: [se houver impedimento]
```

## TDD

RED → GREEN → REFACTOR. Sem exceções. Coverage mínimo: 60%.

## Boundaries

- Todo `tasks.md` declara `_Boundary:_` e `_Depends:_` por task
- Reviewer verifica boundary violations antes de style issues

## Feature Flags

Todo código novo protegido por flag. Default: OFF até `/a-ship`.

## Documentação (Diataxis)

| Tipo | Diretório | Quando criar |
|------|-----------|--------------|
| Tutorial | `docs/tutorial/` | Primeiros passos |
| How-to | `docs/how-to/` | Receitas específicas |
| Reference | `docs/reference/` | API, config |
| Explanation | `docs/explanation/` | Por que funciona assim |

## Safety

- `/careful` antes de operações destrutivas
- `/freeze` durante debug de módulo
- `/guard` em produção

## Idioma

[pt-BR / en-US]
