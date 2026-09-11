---
type: KDD Contract
id: email-agent-sprint56-notification-idempotency
objective: Evitar escrituras en operaciones de reglas sin cambios
status: frozen
---

- eliminar una regla ausente devuelve `False` sin escribir;
- activar una regla ya activa no escribe;
- desactivar una regla ya desactivada no escribe;
- las operaciones no crean reglas por repetición;
- la autorización sigue siendo necesaria aunque el resultado sea no-op.
