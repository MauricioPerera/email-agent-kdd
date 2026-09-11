# Sprint 25 — Siguiente paso del onboarding

## Objetivo

Indicar de forma accionable qué puede hacer el usuario después de completar
la configuración inicial.

## Resultado

- El resumen exitoso incluye `next` localizado en español, inglés o portugués.
- El comando recomendado es `email-agent sync ROOT ACCOUNT_ID`.
- `ROOT` y `ACCOUNT_ID` se mantienen como valores visibles para que el usuario
  pueda reemplazarlos sin que el agente solicite secretos.
- El resultado conserva el resumen público del Sprint 24 y no añade datos
  sensibles.

## Verificación

La prueba congelada valida el JSON exacto y la ausencia de `credential_ref`.
