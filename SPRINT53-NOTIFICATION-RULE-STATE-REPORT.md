# Sprint 53 — Estado de reglas de notificación

## Objetivo

Permitir pausar y reanudar una regla sin perder su filtro.

## Resultado

- `notification disable ROOT NAME CONFIRMAR REGLA` pausa una regla.
- `notification enable ROOT NAME CONFIRMAR REGLA` la reanuda.
- Cada cambio exige confirmación explícita.
- La consulta, el nombre y el archivo se conservan; no se crea una regla nueva.
- La skill instruye a mostrar la regla antes de cada cambio.

## Verificación

La prueba congelada cubre rechazo sin confirmación y el ciclo disable/enable.
