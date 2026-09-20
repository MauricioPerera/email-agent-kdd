# Email Agent v0.2.3

## Novedades

- `query` y las notificaciones locales comparten una gramática de filtros
  determinista, con previsualización de reglas, alertas resumen, enfriamiento
  y estado local de sincronización.
- Las respuestas históricas con asunto `Re:` se reconocen aunque no tengan
  cabeceras de hilo persistidas.

## Correcciones

- Las rutas emitidas por `query` funcionan con `read` y `attachment list` en
  Windows incluso bajo virtualización de directorios.
- El smoke test de instalación offline valida la versión y los artefactos de
  la release actual.

## Verificación

- Suite: 1080 pruebas exitosas, 6 omitidas.
- CI: matriz Windows/macOS/Linux y Python 3.10–3.13 verde.
