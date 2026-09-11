# Sprint 54 — Integridad del almacén de reglas

## Objetivo

Evitar que una configuración de notificaciones corrupta produzca avisos
parciales o sea reparada silenciosamente.

## Resultado

- Cada regla cargada valida nombre, consulta y estado.
- Un filtro corrupto, incluyendo `para:` vacío, invalida el almacén completo.
- El error es genérico para el CLI y detiene la evaluación antes de emitir.
- No se reescribe ni se crea estado nuevo cuando la configuración es inválida.

## Verificación

La prueba congelada cubre carga y evaluación de un almacén corrupto.
