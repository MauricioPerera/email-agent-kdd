# Sprint 45 — Seguridad del payload de notificaciones

## Objetivo

Congelar en la skill el tratamiento seguro del asunto y texto de los avisos
del sistema operativo.

## Resultado

- La skill indica que el texto viaja como dato.
- Prohíbe interpolarlo en scripts o shell.
- Cubre asuntos con comillas, `$()` y saltos de línea.
- La prueba congelada evita que el agente olvide esta frontera.

## Verificación

La batería completa valida la documentación del plugin y sus comandos.
