# Sprint 65 — Paginación de candidatos de contacto

## Objetivo

Permitir resolver libretas grandes sin devolver todos los candidatos en una
sola respuesta.

## Resultado

- `contact find ROOT TEXT` conserva su salida por líneas.
- `--offset` y `--limit` recorren candidatos por lotes de hasta 100.
- `--json` informa total y `next_offset`.
- La búsqueda sigue siendo de solo lectura.

## Verificación

La prueba congelada cubre una página JSON de candidatos.
