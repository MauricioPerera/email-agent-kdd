# Sprint 59 — Consulta exacta de contactos

## Objetivo

Permitir que el agente confirme un contacto concreto antes de usarlo en una
búsqueda.

## Resultado

- `contact show ROOT EMAIL` devuelve un único contacto en JSON.
- La comparación del email es exacta después de recortar espacios y aplicar
  minúsculas.
- Un contacto inexistente produce un error sin crear ni modificar la libreta.
- La consulta no depende del nombre visible, evitando ambigüedades.

## Verificación

La prueba congelada cubre coincidencia normalizada y ausencia sin efectos
secundarios.
