---
type: KDD Contract
id: email-agent-sprint50-plugin-notification-confirmation-scope
objective: Limitar cada confirmacion a una invocacion concreta
status: frozen
---

- `CONFIRMAR REGLA` no es una autorización permanente;
- solo cubre la invocación add/delete que la contiene;
- no se almacena ni se reutiliza en otra operación;
- confirmar una regla no autoriza modificar otra;
- cada nueva mutación requiere su propia confirmación explícita.
