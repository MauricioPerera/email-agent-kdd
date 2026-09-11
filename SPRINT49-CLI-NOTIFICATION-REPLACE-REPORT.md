# Sprint 49 — Reemplazo autorizado de reglas

## Objetivo

Evitar que `notification add` reemplace silenciosamente una regla existente.

## Resultado

- Crear una regla nueva conserva la sintaxis habitual.
- Reemplazar una regla existente requiere mostrar su consulta y confirmar.
- El CLI exige exactamente `CONFIRMAR REGLA` para ese reemplazo.
- Sin confirmación, la regla almacenada permanece intacta.

## Verificación

La prueba congelada cubre creación, rechazo sin mutación y reemplazo autorizado.
