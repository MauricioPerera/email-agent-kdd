# Sprint 55 — Integridad del estado de notificaciones

## Objetivo

Evitar avisos duplicados o pérdida silenciosa del historial cuando el estado
persistido de notificaciones está dañado.

## Resultado

- El estado debe contener una lista de hashes no vacíos.
- Un estado con forma inválida se rechaza antes de evaluar registros.
- No se emiten notificaciones parciales.
- El archivo corrupto no se reescribe ni se repara silenciosamente.

## Verificación

La prueba congelada valida detención previa, ausencia de avisos y preservación
del archivo corrupto.
