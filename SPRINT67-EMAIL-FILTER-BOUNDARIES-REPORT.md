# Sprint 67 — Límites exactos de filtros de email

## Objetivo

Evitar falsos positivos por subcadenas al buscar contactos o destinatarios.

## Resultado

- `contact:EMAIL` exige límites de dirección en `From`, `To` y `Cc`.
- `para:EMAIL` exige límites de dirección en `delivered_to`.
- Una dirección más larga que contiene el texto consultado no coincide.
- Se mantienen la comparación casefold y la preservación de puntos y `+tag`.

## Verificación

La prueba congelada cubre una dirección extendida que no debe coincidir.
