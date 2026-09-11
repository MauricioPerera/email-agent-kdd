# Sprint 40 — Primer sync paginado para agentes

## Objetivo

Evitar que el primer uso intente procesar un buzón grande en una sola
ejecución.

## Resultado

- La skill recomienda `email-agent sync ROOT ACCOUNT_ID --limit 50`.
- Documenta `--unread` para el caso solicitado por el usuario.
- Indica continuar con ejecuciones posteriores y el cursor almacenado.
- Mantiene la prohibición de solicitar o inferir credenciales.

## Verificación

La prueba congelada exige que la skill documente la página, el filtro de no
leídos y el comando completo.
