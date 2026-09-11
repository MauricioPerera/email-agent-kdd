# Sprint 34 — Skill del plugin para onboarding

## Objetivo

Hacer que un agente pueda descubrir y usar correctamente el onboarding
automático y sus opciones seguras.

## Resultado

- La skill recomienda `onboard ROOT` para el primer uso.
- Documenta `--gui`, `--terminal` y `--lang es|en|pt`.
- Explica que el resumen contiene solo metadatos públicos.
- Reitera que el agente nunca debe solicitar, imprimir o completar secretos.

## Verificación

La prueba congelada del manifiesto ahora exige que la skill documente
`onboard` como comando disponible.
