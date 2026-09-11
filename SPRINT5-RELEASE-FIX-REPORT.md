# SPRINT5 — Corrección de release

Fecha: 2026-09-11 · Origen: `SPRINT5-RELEASE-AUDIT.md` (A2, M1, M2, criterio de aceptación). Sin commit ni push. Alcance: `pytest.ini`, `pyproject.toml`, `.github/workflows/ci.yml`, `docs/RELEASE.md`. README sin cambios (ver §5).

## 1. Configuración pytest unificada (A2/B4)

- `pytest.ini` — fuente única, ahora con `testpaths`:
  ```ini
  [pytest]
  python_files = frozen_*.py
  testpaths = outputs/email-agent-kdd/tests
  addopts = --import-mode=importlib
  ```
- `pyproject.toml` — eliminada la sección muerta `[tool.pytest.ini_options]` (pytest la ignoraba al existir pytest.ini); el resto del packaging intacto.

## 2. CI actualizada (M1)

`.github/workflows/ci.yml`:

- Job `test` (matriz Windows/macOS/Linux × Python 3.10–3.13): añade `python -m pip install .` + `email-agent --help` (shell bash) tras los existentes `compileall -q src` y `pytest -q`.
- Job `build` (3 OS, Python 3.12): `pip install build` + `python -m build` con aislamiento (reproducible), verifica que existan `dist/*.tar.gz` y `dist/*.whl`; **sin subir artefactos** ni publicar.
- Job `hygiene` (ver §3).
- Validado YAML con PyYAML.

## 3. Job de higiene (M2)

Job `hygiene` en ubuntu-latest: recorre `git ls-files -z` y falla (exit 1) si algún archivo trackeado coincide con `store/*`, `work/*`, `drafts/*`, `.email-agent/*`, `build/*`, `*.egg-info/*`, `*.key`, `*.pem`, `*.p12`, `*.pfx`, `.env`/`.env.*`/`*.env`, `credentials*.json`, `*credentials*.json`, `secret*`, `.secrets/*`, `id_rsa*`, `*.ppk`, `*_rsa`, `auth.json`, `*.crt`. Solo imprime patrón + conteo (`FORBIDDEN: N tracked file(s) match pattern: X`): nunca rutas ni contenido sensible.

## 4. docs/RELEASE.md reescrito

Ahora distingue lo automatizado (los 4 pasos de CI: compileall, pytest con la config única, `pip install .` + `--help`, `python -m build` sin publicación, y el job de higiene como red de seguridad) de lo manual (commit/push de los 49 pendientes, licencia/propietario, revisión de datos locales, tag semántico + hashes, marketplace del plugin). Se conserva la nota de que la publicación requiere decisión del propietario.

## 5. README

Sin contradicciones de instalación/CI: los comandos (`pip install .`, `pipx install .`, `installers/`) coinciden con `pyproject.toml` y los installers. El único hallazgo de la auditoría sobre README (M3, detalles internos de `imap_deletion.py` en la sección de usuario) no es de instalación/CI: fuera del alcance pedido, sin cambios.

## Comandos de verificación (todos ejecutados)

| Comando | Resultado |
|---|---|
| `python -m pytest --collect-only` | 712 tests, todos en `outputs/email-agent-kdd/tests`; 0 rutas de `work/` (antes 741 barría el árbol, incl. `work/ccdd-stage/`) |
| `python -m compileall -q src` | OK |
| `python -m pytest -q` | 712 passed en 4.21s |
| `pip install .` en venv temporal + `email-agent --help` | SMOKE-OK |
| `python -m build` en venv temporal | sdist + wheel generados (`email_agent_cli-0.1.0.tar.gz`, `email_agent_cli-0.1.0-py3-none-any.whl`), BUILD-OK |
| Job de higiene ejecutado en local | OK: 0 archivos trackeados coinciden con los patrones (171 trackeados) |
| YAML de `ci.yml` | Válido |

## Estado

**LISTO** (en disco). Pendiente para release real: commit/push de los 49 archivos pendientes (A1, decisión del propietario — fuera del alcance de esta corrección). CI solo verá el estado tras ese commit.