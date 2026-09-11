# Sprint 66 — Contactos por encabezado

## Objetivo

Evitar falsos positivos al buscar conversaciones por contacto.

## Resultado

- `contact:EMAIL` solo inspecciona `From`, `To` y `Cc` del frontmatter.
- Una dirección mencionada únicamente en el cuerpo no coincide.
- Se mantiene la comparación insensible a mayúsculas.
- `para:EMAIL` conserva su semántica de destinatario real.

## Verificación

La prueba congelada cubre un contacto en encabezado y un falso positivo en el cuerpo.
