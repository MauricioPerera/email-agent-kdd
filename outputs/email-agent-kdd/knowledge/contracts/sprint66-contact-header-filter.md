---
type: KDD Contract
id: email-agent-sprint66-contact-header-filter
objective: Buscar contactos solo en encabezados de mensaje
status: frozen
---

- `contact:EMAIL` inspecciona `from`, `to` y `cc`;
- el cuerpo no satisface el filtro de contacto;
- la coincidencia ignora mayúsculas;
- el filtro sigue siendo combinable por AND;
- `para:EMAIL` no cambia su contrato.
