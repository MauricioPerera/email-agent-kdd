# Sprint 60 — Candidatos de contacto

## Objetivo

Facilitar la resolución asistida de un nombre o email parcial sin inventar una
identidad.

## Resultado

- `contact find ROOT TEXT` busca en nombre y email.
- Devuelve una línea JSON por candidato.
- La búsqueda ignora mayúsculas y espacios exteriores.
- El agente debe pedir selección cuando hay varios candidatos.
- La operación es de solo lectura y no cambia `contacts.json`.

## Verificación

La prueba congelada cubre coincidencias múltiples y texto vacío.
