# SPRINT11-RELEASE-DOCS-REPORT

Fecha: 2026-09-11 · Ámbito: documentación de release (Sprint 11). Sin cambios de código funcional, sin commit/push/publicación, sin red (solo verificaciones locales), sin secretos ni datos locales en los docs.

## Veredicto

LISTO. Auditados `pyproject.toml`, `plugins/email-agent/.codex-plugin/plugin.json`,
`README.md`, `SECURITY.md` y `docs/RELEASE.md` contra la salida real de la CLI y la
suite congelada. Creado `CHANGELOG.md` (nuevo) y reescrita la checklist de
`docs/RELEASE.md`. Todas las verificaciones locales en verde.

## Verificaciones locales ejecutadas

| Verificación | Resultado |
|---|---|
| `python -m pytest -q` (suite completa congelada) | **793 passed** (0 cambios desde sprints previos; sprint 5 cerró con 724 y los sprints 8–10 añadieron los restantes) |
| `python -m compileall -q src` | OK, sin errores |
| `python -m build` | OK: `email_agent_cli-0.1.0.tar.gz` + `email_agent_cli-0.1.0-py3-none-any.whl` |
| Smoke del wheel: `pip install --target <tmp>` + entry point | OK: `email-agent --help` responde desde el wheel instalado |
| `from src.email.cli import main` importable | OK (`ENTRY_OK`) |
| Comparación `--help` ↔ README ↔ SKILL.md | Coincide comando a comando (sync con `--attachments`, `message remote-*`, `attachment list/download/gc`, `account setup/setup-gui/remove/list`, `startup`, `draft/send`) |
| `frozen_plugin_manifest.py` | Incluido en la suite verde; valida semver estricto de la versión del plugin |

## Auditoría

### `pyproject.toml`

- `email-agent-cli` **0.1.0**, `requires-python >=3.10`, **cero dependencias**,
  entry point `src.email.cli:main`. Coherente con CI (matriz 3.10–3.13) y con la
  versión del plugin. Sin cambios necesarios.
- Nota no bloqueante: Python 3.14 no está en la matriz de CI ni probado en local.

### `plugins/email-agent/.codex-plugin/plugin.json`

- Versión **0.1.0** (coincide con `pyproject.toml`), semver válido
  (`frozen_plugin_manifest.py` en verde). `interface.longDescription/capabilities`
  correctos tras el sprint 7, `defaultPrompt` como lista, `skills: "./skills"`.
  Descripción actual refleja sync paginado, papelera, adjuntos y envíos/borrados
  con confirmación literal. Sin cambios.

### `.agents/plugins/marketplace.json`

- Catálogo apunta a `./plugins/email-agent` local, `installation: AVAILABLE`.
  Sin campo de versión (el esquema no lo exige). Sin cambios.

### `README.md`

- Sin claims falsos detectados: comandos, frases literales de confirmación, límites
  de adjuntos (25 MB / 100 MB / `SYNC_ATTACHMENT_BUDGET_MB`), `TRASH_MAILBOX`
  obligatorio, `UIDPLUS` para `remote-purge`, almacenes de credenciales nativos y
  rollback de `account remove` coinciden con la implementación y la CLI.
- Falta menor, no corregida (fuera de alcance de este sprint): no se menciona que
  `account setup-gui` requiere tkinter ni que Python 3.14 no está testado. Ambos
  quedan documentados en la sección "Limitaciones conocidas" de `CHANGELOG.md` y en
  la checklist de `docs/RELEASE.md`.

### `SECURITY.md`

- Coherente con el sprint 9 (almacenes nativos sin fallback) y el sprint 10
  (desvinculación transaccional con rollback best-effort). Sin cambios.

## Archivos creados/modificados

- **`CHANGELOG.md` (nuevo)** — entrada única `0.1.0 (sin publicar)` con lo añadido/
  corregido por sprint (1: papelera local + índices + exclusión `.trash` en
  búsqueda; 2: borrado remoto IMAP; 3: adjuntos —metadatos, list, download,
  asociación, vínculo sync; 4: `sync --attachments` + `attachment gc`;
  5: auditoría/corrección de release; 6: plugin e instaladores con verificación;
  7: validación oficial del manifiesto; 8: onboarding verificado; 9: credenciales
  nativas multi-OS + GUI multiplataforma; 10: desvinculación transaccional), más
  sección de limitaciones conocidas y de migraciones (vía soportada: re-sync para
  nodos legacy; sin conversión automática).
- **`docs/RELEASE.md` (actualizado)** — checklist de release en 4 bloques:
  1) pre-commit local (pytest 793, compileall, build, higiene de datos/secretos);
  2) coherencia de versión y manifiestos (pyproject ↔ plugin.json ↔ CHANGELOG,
     semver estricto);
  3) documentación fiel a las funciones de los sprints 1–10 (comandos reales de la
     CLI, cinco frases literales de confirmación, tres almacenes de credenciales,
     limitaciones conocidas y migraciones);
  4) publicación (commit/push, tag semántico, hashes, marketplace, instaladores).
- Sin cambios en código, README, SECURITY.md, plugin.json ni pyproject.toml.

## Fuentes usadas (sin inventar claims)

Solo reportes existentes de los sprints 1–10 (fechas reales: 2026-09-10 y
2026-09-11), la salida verificada de `email-agent --help`, el resultado de la suite
(793 passed) y el contenido actual de README/SECURITY/docs. Ningún número de
versión, fecha, límite o comando fue estimado: cada uno está respaldado por
`pyproject.toml`, `plugin.json`, la CLI o el test congelado correspondiente.