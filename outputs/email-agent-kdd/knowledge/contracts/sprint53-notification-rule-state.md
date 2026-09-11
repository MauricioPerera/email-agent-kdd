---
type: KDD Contract
id: email-agent-sprint53-notification-rule-state
objective: Pausar y reanudar reglas con confirmacion
status: frozen
---

- deshabilitar requiere `CONFIRMAR REGLA`;
- habilitar requiere `CONFIRMAR REGLA`;
- rechazo sin confirmación no muta la regla;
- cambiar el estado conserva nombre y consulta;
- una regla ausente devuelve error sin crearla.
