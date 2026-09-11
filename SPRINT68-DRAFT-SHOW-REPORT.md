# Sprint 68 — Vista previa segura de borradores

## Objetivo KDD

Permitir que un usuario revise el borrador exacto antes de autorizar un envío.

## Resultado

Se añadió `draft show ROOT DRAFT_ID`. El comando valida que el identificador tenga
el formato sha256, lee únicamente el JSON esperado dentro de `ROOT/drafts` y
devuelve su contenido en JSON. No contacta al proveedor, no resuelve secretos y
no escribe ni cambia el estado del borrador.

El skill del plugin ahora exige mostrar esta vista previa antes de pedir la frase
literal `CONFIRMAR ENVIO`. Se congelaron pruebas para éxito sin mutación,
identificador inseguro y borrador inexistente.

## Verificación

- `python -m pytest -q`
- `git diff --check`

