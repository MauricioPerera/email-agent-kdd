# Sprint 37 — Idioma inválido en setup

## Objetivo

Aplicar al asistente de terminal la misma validación previa y sin efectos
secundarios ya garantizada por `onboard`.

## Resultado

- `account setup ROOT --lang xx` devuelve error de argumentos.
- No lee entradas del usuario ni crea `accounts.json`.
- El mensaje indica los idiomas aceptados.

## Verificación

Se añadió una prueba congelada con una entrada que debe permanecer sin llamar.
