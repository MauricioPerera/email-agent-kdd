# Sprint 33 — Descubribilidad del idioma en setup

## Objetivo

Hacer visible en la ayuda de la CLI que el asistente de terminal admite un
idioma explícito.

## Resultado

- La ayuda general documenta `account setup ROOT --lang es|en|pt`.
- El uso principal también refleja la opción.
- El cambio no altera la sintaxis existente ni el comportamiento por defecto.

## Verificación

La prueba congelada comprueba que la opción aparece en `email-agent --help`.
