---
type: KDD Contract
id: email-agent-sprint54-notification-rule-store
objective: Rechazar almacenes de reglas corruptos sin efectos secundarios
status: frozen
---

- cada regla debe tener nombre válido, consulta válida y estado booleano;
- una regla inválida invalida la carga completa;
- la evaluación no emite avisos parciales;
- la evaluación no reescribe reglas corruptas;
- no se crea estado de notificación después de detectar corrupción.
