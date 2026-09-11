---
type: KDD Contract
id: email-agent-sprint65-contact-find-pagination
objective: Paginar candidatos de contacto
status: frozen
---

- `contact find` conserva la salida por líneas sin opciones;
- `--offset` es mayor o igual a cero;
- `--limit` está entre 1 y 100;
- `--json` contiene total, offset, limit, results y next_offset;
- la búsqueda no muta la libreta.
