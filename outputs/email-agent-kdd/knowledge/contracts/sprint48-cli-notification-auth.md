---
type: KDD Contract
id: email-agent-sprint48-cli-notification-auth
objective: Hacer ejecutable la confirmacion de borrado de reglas
status: frozen
---

- listar reglas no requiere confirmación ni muta el almacén;
- borrar sin `CONFIRMAR REGLA` devuelve error de argumentos;
- borrar sin confirmación no escribe ni elimina la regla;
- `CONFIRMAR REGLA` debe ser literal y ocupar los argumentos finales;
- borrar confirmado devuelve un recibo JSON y elimina solo la regla indicada.
