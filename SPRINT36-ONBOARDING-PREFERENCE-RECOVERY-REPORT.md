# Sprint 36 — Recuperación de preferencias corruptas

## Objetivo

Verificar que el primer uso siga siendo seguro cuando la preferencia local de
idioma no sea legible.

## Resultado

- `onboard` usa el idioma detectado como fallback.
- El diagnóstico continúa y comunica su estado normal.
- El contenido corrupto no se copia al resultado.
- No se inicia configuración si hay requisitos pendientes.

## Verificación

Se añadió una prueba congelada con una preferencia JSON inválida y un marcador
ficticio que debe permanecer fuera de la salida.
