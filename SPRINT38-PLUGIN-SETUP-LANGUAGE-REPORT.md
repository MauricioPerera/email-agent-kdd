# Sprint 38 — Skill del setup localizado

## Objetivo

Documentar en el plugin la ruta directa para ejecutar el asistente de
terminal en un idioma elegido.

## Resultado

- La skill conserva `account setup ROOT` como ruta compatible.
- También documenta `account setup ROOT --lang es|en|pt`.
- La prueba del manifiesto congela esta sintaxis para evitar regresiones.

## Verificación

La batería completa valida skill, manifiesto, CLI e instaladores.
