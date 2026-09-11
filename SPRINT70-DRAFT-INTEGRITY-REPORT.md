# Sprint 70 — Integridad del borrador antes del envío

## Objetivo KDD

Garantizar que el contenido autorizado por el usuario sea el mismo contenido
que llegará al servidor SMTP.

## Resultado

Antes de enviar, la CLI recalcula el ID determinista a partir de la cuenta,
destinatarios, asunto y cuerpo persistidos. Si el ID de la ruta, el `id` interno
y el contenido no coinciden, la operación termina sin red, sin reparar el archivo
y sin solicitar reintentos automáticos.

## Verificación

- `python -m pytest -q`
- `git diff --check`
