# Sprint 52 — Validación de filtros de notificación

## Objetivo

Evitar guardar reglas de notificación ambiguas o imposibles de evaluar.

## Resultado

- Se rechazan filtros vacíos o compuestos solo por espacios.
- Se rechazan controles invisibles, incluidos saltos de línea.
- Se rechaza el token `para:` sin una dirección.
- El rechazo ocurre antes de crear o modificar el archivo de reglas.
- La dirección completa, incluidos puntos y `+tag`, sigue conservándose.

## Verificación

La prueba congelada valida el rechazo previo al almacenamiento y la ausencia de
efectos secundarios.
