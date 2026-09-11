# Sprint 51 — Inspección segura de reglas

## Objetivo

Permitir que el agente muestre una regla concreta antes de solicitar una
confirmación de reemplazo o eliminación.

## Resultado

- `notification show ROOT NAME` es de solo lectura.
- Devuelve la regla exacta en JSON, incluidos nombre, consulta y estado.
- Una regla inexistente produce un error sin crear ni modificar archivos.
- La skill instruye al agente a usar `show` antes de una mutación.

## Verificación

La prueba congelada cubre inspección exacta y ausencia sin efectos secundarios.
