# Sprint 64 — Salida JSON de candidatos

## Objetivo

Facilitar al agente la resolución de contactos con una respuesta estructurada.

## Resultado

- `contact find ROOT TEXT --json` devuelve `total` y `results`.
- La salida tradicional de una línea JSON por candidato permanece disponible.
- La búsqueda sigue siendo de solo lectura.
- Un resultado múltiple continúa requiriendo una elección explícita antes de
  buscar conversaciones o enviar.

## Verificación

La prueba congelada cubre candidatos y total en formato JSON.
