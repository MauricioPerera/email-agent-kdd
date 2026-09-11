# Sprint 73 — Instaladores fijados a la release estable

## Objetivo KDD

Reducir el riesgo de que un usuario nuevo instale accidentalmente código de una
rama mutable y ofrecer un camino claro desde la release pública.

## Resultado

`install.ps1` acepta `-Ref` y `install.sh` acepta una segunda posición para la
referencia. Ambos usan `v0.1.0` por defecto, conservan la comprobación de Python,
pip y `email-agent --help`, y no manejan credenciales.

El marketplace mantiene la referencia GitHub `v0.1.0`. La instalación limpia se
probó descargando el wheel de la GitHub Release en un entorno virtual aislado y
ejecutando `email-agent --help`, sin credenciales.

## Verificación

- `python -m pytest -q` — 976 pruebas.
- `git diff --check`.
- CI multiplataforma pendiente para este commit.
