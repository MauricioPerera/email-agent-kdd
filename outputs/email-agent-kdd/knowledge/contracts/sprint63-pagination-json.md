---
type: KDD Contract
id: email-agent-sprint63-pagination-json
objective: Exponer metadatos de paginacion en JSON
status: frozen
---

- `--json` devuelve un único objeto JSON;
- el objeto contiene `total`, `offset`, `limit`, `results` y `next_offset`;
- `results` conserva el orden determinista;
- `next_offset` indica la siguiente página o `null`;
- sin `--json` se conserva una ruta por línea.
