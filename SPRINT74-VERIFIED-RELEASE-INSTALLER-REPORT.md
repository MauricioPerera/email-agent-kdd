# Sprint 74 — Instalador desde release con verificación

## Objetivo KDD

Reducir la fricción para usuarios no técnicos y evitar que la instalación normal
dependa de Git o de una rama mutable.

## Resultado

Los instaladores descargan el wheel `v0.1.0` y `SHA256SUMS.txt` desde GitHub,
comparan el SHA-256 local con el hash publicado y solo después invocan pip con
`--no-index`. Una discrepancia detiene el flujo. El modo de desarrollo queda
separado y explícito: `-FromSource` en Windows y `--source` en macOS/Linux.

La prueba congelada valida estas garantías sin red ni credenciales; la instalación
real desde el wheel de la release ya se comprobó en un entorno virtual aislado.

## Verificación

- `python -m pytest -q` — 977 pruebas.
- `git diff --check`.
- CI multiplataforma pendiente para este commit.
