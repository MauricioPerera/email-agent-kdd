---
type: KDD Contract
id: email-agent-sprint61-query-pagination
objective: Paginar resultados de busquedas locales
status: frozen
---

- `query ROOT INSTRUCTION` conserva su comportamiento;
- `--offset` es entero mayor o igual a cero;
- `--limit` es entero entre 1 y 100;
- cada lote preserva el orden lexicográfico;
- opciones inválidas se rechazan antes de consultar archivos.
