# Sprint 63 — Recibos JSON de paginación

## Objetivo

Dar al agente información explícita para continuar una búsqueda paginada.

## Resultado

- `query` y `search` aceptan `--json` junto con sus opciones de página.
- El recibo incluye `total`, `offset`, `limit`, `results` y `next_offset`.
- `next_offset` es `null` en la última página.
- La salida tradicional de una ruta por línea no cambia.

## Verificación

La prueba congelada cubre el avance de página y el final del recorrido.
