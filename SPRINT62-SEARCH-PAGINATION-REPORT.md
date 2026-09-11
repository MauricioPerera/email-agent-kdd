# Sprint 62 — Paginación de `search`

## Objetivo

Evitar que una búsqueda léxica grande devuelva todos sus resultados en una
sola operación.

## Resultado

- `search ROOT QUERY` conserva su comportamiento actual.
- `--offset N` y `--limit N` permiten recorrer resultados por lotes.
- El límite acepta entre 1 y 100 resultados.
- Los resultados mantienen el orden determinista.
- Los parámetros inválidos se rechazan antes de leer archivos.

## Verificación

La prueba congelada cubre cortes estables y rechazo del límite inválido.
