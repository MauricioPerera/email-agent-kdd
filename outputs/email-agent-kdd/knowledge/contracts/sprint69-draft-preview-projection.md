---
type: KDD Contract
id: email-agent-sprint69-draft-preview-projection
objective: Evitar la exposición de campos inesperados en una vista previa
status: frozen
---

- `draft show` solo devuelve `id`, `account_id`, `to`, `subject`, `body` y `status`;
- campos adicionales del JSON persistido no llegan a stdout;
- las credenciales y sus referencias nunca forman parte de la vista previa;
- la proyección no modifica el borrador almacenado.
