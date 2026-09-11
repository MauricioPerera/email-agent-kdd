# Sprint 31 — Validación segura del idioma

## Objetivo

Evitar efectos secundarios cuando el usuario indique un idioma inválido al
iniciar el onboarding.

## Resultado

- `onboard ROOT --lang xx` devuelve error de argumentos.
- No ejecuta diagnóstico, GUI, asistente de terminal ni escritura de
  preferencias.
- El mensaje indica los valores aceptados: `es`, `en` y `pt`.

## Verificación

Se añadió una prueba congelada que comprueba código, ausencia de llamadas y
ausencia del archivo de preferencias.
