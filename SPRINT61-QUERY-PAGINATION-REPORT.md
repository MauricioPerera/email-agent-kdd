# Sprint 61 — Paginación de búsquedas

## Objetivo

Permitir recorrer resultados grandes de `query` por lotes acotados.

## Resultado

- `query` conserva su forma actual sin opciones.
- `--offset N` permite continuar desde una posición estable.
- `--limit N` limita cada lote a 1–100 resultados.
- Los resultados conservan el orden determinista del buscador.
- Valores inválidos se rechazan antes de leer el almacén.

## Verificación

La prueba congelada cubre cortes estables y valores inseguros.
