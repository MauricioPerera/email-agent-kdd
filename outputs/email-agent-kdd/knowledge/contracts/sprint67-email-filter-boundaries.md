---
type: KDD Contract
id: email-agent-sprint67-email-filter-boundaries
objective: Evitar coincidencias parciales de direcciones
status: frozen
---

- los filtros de email comparan direcciones delimitadas;
- una dirección más larga no satisface una dirección más corta;
- `contact:` conserva su fuente en encabezados;
- `para:` conserva su fuente en `delivered_to`;
- puntos, mayúsculas y `+tag` mantienen su semántica documentada.
