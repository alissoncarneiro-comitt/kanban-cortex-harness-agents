# Tasks — {{FEATURE_ID}}

> Cada task tem `_Boundary:_` (escopo) e `_Depends:_` (dependências).
> Implementação: 1 task por iteração. TDD RED → GREEN.

## Task 1: [Título descritivo]
**Owner**: Engineer
**Estimate**: [X]h
**_Boundary:_** `src/features/{{feature}}/api/routes.ts` + `validators.ts`
**_Depends:_** None

### Acceptance
- [ ] Testes unitários passam (RED → GREEN)
- [ ] Validação cobre todos os casos de erro do design.md
- [ ] Feature flag criada: `{{feature}}_api_v1`

### Implementation Notes
[Preenchendo durante /a-build. Aprendizados propagam para próximas tasks.]

---

## Task 2: [Título descritivo]
**Owner**: Engineer
**Estimate**: [X]h
**_Boundary:_** `src/features/{{feature}}/service/index.ts`
**_Depends:_** Task 1

### Acceptance
- [ ] Business logic cobre todos os paths do state machine
- [ ] Testes de integração com repository mockado
- [ ] Feature flag ativa: `{{feature}}_service_v1`

---

## Task 3: [Título descritivo]
**Owner**: Engineer
**Estimate**: [X]h
**_Boundary:_** `src/features/{{feature}}/repository/index.ts`
**_Depends:_** Task 2

### Acceptance
- [ ] Migrations criadas e reversíveis
- [ ] Testes de integração com DB real (test container)
- [ ] Rollback script validado

---

## Task N: [UI/Frontend se houver]
**Owner**: Engineer + Designer
**Estimate**: [X]h
**_Boundary:_** `src/features/{{feature}}/components/`
**_Depends:_** Task 1 (API contrato definido)

### Acceptance
- [ ] Componentes seguem design system
- [ ] A11y: keyboard navigation + screen reader
- [ ] Responsivo: mobile + desktop
- [ ] Storybook stories criadas
