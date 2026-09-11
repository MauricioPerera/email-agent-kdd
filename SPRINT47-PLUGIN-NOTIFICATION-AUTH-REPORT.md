# Sprint 47 — Autorización de reglas de notificación

## Objetivo

Fijar el límite de autorización para que un agente pueda consultar reglas de
notificación, pero solo cree, cambie o elimine reglas con intención explícita
del usuario.

## Resultado

- Crear una regla requiere que el usuario solicite esa regla exacta.
- Listar reglas queda definido como operación de solo lectura.
- Eliminar una regla exige mostrar su nombre y consulta exacta y recibir una
  confirmación inmediata.
- El agente no infiere, amplía, sustituye ni elimina filtros por conveniencia.
- Las direcciones y consultas permanecen como datos exactos, sin normalización
  inventada.

## Verificación

La prueba congelada del manifiesto valida que la skill documente estas
fronteras de autorización.
