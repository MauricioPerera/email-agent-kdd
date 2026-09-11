# Sprint 57 — Límite de reglas de notificación

## Objetivo

Evitar configuraciones locales ilimitadas que degraden la evaluación o sean
creadas por error por una automatización.

## Resultado

- El almacén acepta como máximo 100 reglas.
- Crear una regla 101 produce un error antes de escribir.
- Reemplazar una regla existente sigue permitido dentro del límite.
- El límite no elimina ni desactiva reglas automáticamente.

## Verificación

La prueba congelada cubre el límite, el rechazo y el reemplazo permitido.
