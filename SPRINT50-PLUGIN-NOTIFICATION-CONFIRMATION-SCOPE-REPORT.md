# Sprint 50 — Alcance de confirmación de reglas

## Objetivo

Evitar que la confirmación de una mutación de reglas se interprete como una
autorización permanente o transferible.

## Resultado

- `CONFIRMAR REGLA` solo autoriza la invocación concreta que lo contiene.
- El agente no guarda ni reutiliza la confirmación.
- La confirmación de una regla no autoriza otra regla o acción.
- La frontera queda documentada en la skill y congelada por prueba.

## Verificación

La batería local valida la redacción contractual del alcance de confirmación.
