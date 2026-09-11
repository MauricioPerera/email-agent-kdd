# Sprint 69 — Proyección segura de la vista previa

## Objetivo KDD

Impedir que campos inesperados de un borrador local aparezcan al mostrarlo al
usuario o al agente.

## Resultado

`draft show` ahora devuelve una lista cerrada de campos públicos: identificador,
cuenta, destinatarios, asunto, cuerpo y estado. Ignora campos adicionales sin
alterar el archivo persistido, incluyendo referencias de credenciales o notas
internas.

## Verificación

- `python -m pytest -q`
- `git diff --check`
