---
type: KDD Contract
id: email-agent-sprint62-search-pagination
objective: Paginar resultados de search
status: frozen
---

- `search ROOT QUERY` conserva su salida;
- `--offset` es entero mayor o igual a cero;
- `--limit` está entre 1 y 100;
- cada lote conserva el orden lexicográfico;
- parámetros inválidos no disparan lecturas del almacén.
