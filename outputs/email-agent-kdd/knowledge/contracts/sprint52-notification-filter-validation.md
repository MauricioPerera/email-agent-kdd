---
type: KDD Contract
id: email-agent-sprint52-notification-filter-validation
objective: Validar filtros antes de persistir reglas
status: frozen
---

- un filtro vacío o en blanco se rechaza;
- controles ASCII se rechazan antes de escribir;
- `para:` sin dirección se rechaza;
- un filtro inválido no crea ni reemplaza una regla;
- las direcciones válidas se almacenan sin normalización inventada.
