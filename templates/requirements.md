# Requirements — {{FEATURE_ID}}

> Format: EARS (Easy Approach to Requirements Syntax)

## Functional Requirements

### {{REQ_ID_1}} — [Título]
**Type**: Functional | Non-Functional | Constraint

The {{system_name}} shall {{capability}} when {{condition}}.

- **Acceptance Criteria**:
  1. [Critério testável 1]
  2. [Critério testável 2]
- **Priority**: Must | Should | Could | Won't
- **Boundary**: [Qual módulo/arquivo toca]
- **Depends**: [Requisitos que devem existir antes]

## Non-Functional Requirements

### {{NFR_ID_1}} — Performance
The system shall respond to {{operation}} within {{X}} ms under {{load condition}}.

### {{NFR_ID_2}} — Security
The system shall {{security requirement}}.

## Constraints
- [Tecnologia obrigatória]
- [Compliance necessário]
- [Limitação de infraestrutura]

## Traceability Matrix
| Requirement | Design Section | Test Case | Status |
|-------------|--------------|-----------|--------|
| {{REQ_ID_1}} | [Seção] | [TC-001] | Planned |
