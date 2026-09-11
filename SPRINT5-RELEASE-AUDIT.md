# SPRINT5 — Auditoría de release

Fecha: 2026-09-11 · Alcance: solo lectura de `pyproject.toml`, `pytest.ini`, `README.md`, `SECURITY.md`, `docs/RELEASE.md`, `.gitignore`, `.github/`, `installers/`, `src/email/__main__.py` y primer nivel. Sin red, sin modificaciones.

## Resumen

El proyecto es publicable en su estado actual con reservas. Un checkout limpio instala `email-agent` correctamente (paquete `email-agent-cli` v0.1.0, entry point `src.email.cli:main` verificado importable y callable, `src/` y `src/email/` con `__init__.py`, dependencias externas cero). Los comandos documentados en README (sync `--attachments`, `attachment list/download/gc`, `startup install/status/remove`, `message delete/trash/restore/purge/remote-*`) existen todos en la CLI y coinciden con la ayuda del programa; sin secretos ni datos locales trackeados. Los riesgos principales no bloqueantes: duplicación de configuración pytest (pytest.ini anula `[tool.pytest.ini_options]` de pyproject, dejando la recolección sin `testpaths` y barriendo el árbol), y 41 archivos sin commit (incluidos varios tests congelados que CI no verá y 8 fuentes de `src/` modificadas sin subir).

## Hallazgos

### Alta

- **A1 — 41 archivos sin trackear y 8 modificados sin commit.** `git status` muestra 49 entradas: los tests congelados de los sprints 1–4 (`outputs/email-agent-kdd/tests/frozen_*.py`, incl. attachments, sync-attachments, deletion-index, message-deletion, trash-search-exclusion) y todos los informes `*REPORT.md` son `??`; `README.md`, `src/email/cli.py`, `imap_reader.py`, `persist.py`, `persist_at.py`, `query.py`, `search.py` y el plugin están `M`. Un checkout limpio de `origin/main` no contendrá esos tests ni el código modificado: CI validaría una versión distinta (y posiblemente menor) de la que existe en disco. Bloqueante de release hasta commit/push.
- **A2 — Configuración pytest duplicada y conflictiva.** Existen `pytest.ini` (`python_files = frozen_*.py`, `addopts`) y `[tool.pytest.ini_options]` en `pyproject.toml` (`testpaths`). pytest ignora la sección de pyproject al existir pytest.ini, por lo que `testpaths = ["outputs/email-agent-kdd/tests"]` está muerto: la recolección barre el árbol entero. Verificado: `python -m pytest --collect-only` recoge 741 tests, incluidos los de `work/ccdd-stage/` (directorio local gitignored). En un checkout limpio funciona (no hay `work/`), pero el set de tests es distinto entre máquina local y CI, y cualquier directorio futuro con archivos coincidentes entra en CI sin control.

### Media

- **M1 — CI no valida el empaquetado ni el entry point.** `.github/workflows/ci.yml` instala solo `pytest`; nunca ejecuta `pip install .`, por lo que el script `email-agent` no se prueba en CI (el RELEASE.md paso 6 "probar instalación limpia en Windows, macOS y Linux" no está automatizado ni cubierto por el matrix). Tampoco ejecuta `python -m build` (paso 4 de RELEASE.md): un empaquetado roto solo se detectaría al publicar.
- **M2 — `docs/RELEASE.md` menciona revisiones no automatizadas.** Los pasos 1–2 (revisar datos bajo `.email-agent/`, `store/`, `drafts/`, `work/`) son procedimiento manual sin guardián en CI. Hoy no hay nada trackeado (`git ls-files` no devuelve entradas de esos directorios), pero nada impide que una futura adición con `-f` entre al repo.
- **M3 — README expone detalles de implementación en sección de usuario.** "Papelera remota (IMAP)" documenta `src/email/imap_deletion.py`, `MailDeletionProvider`, `ImapDeletionProvider`, `connection_factory` y la constante `TRASH_MAILBOX`: son detalles internos (que además obligan a acoplar README a un fichero de `src/`); a nivel de usuario basta el contrato de comandos y garantías.

### Baja

- **B1 — Nombre de paquete raíz `src`.** `packages.find include = ["src", "src.*"]` instala un paquete top-level llamado `src` en site-packages (contaminación de namespace, colisiones con otros proyectos). Funciona y el entry point resuelve, pero es frágil. Reestructurar a `email_agent/` o `src/`-layout con `[tool.setuptools] package-dir = {"" = "src"}` es un cambio de release futura, no de esta.
- **B2 — Excepciones de .gitignore sin efecto.** `!src/email/credentials.py`, `!src/email/contact_store.py`, `!src/email/account_store.py` no están negados por ninguna regla previa (`credentials*.json`, `secret*`, `*.key` no los cubren); las negaciones sobran. Ruido, sin riesgo.
- **B3 — Clutter de primer nivel.** 13 informes `*SPRINT*/IMPLEMENT-*.md` en la raíz acompañan a `docs/`; para release pública convendría moverlos a `docs/reports/` o excluirlos. No se empaquetan en wheel/sdist, así que no afectan al artefacto.
- **B4 — `pytest.ini` sin `testpaths`.** Aun si se conserva pytest.ini, la ausencia de testpaths es la causa práctica de A2.
- **B5 — `tests/` raíz vacía** (solo `__pycache__/`, sin trackear): candidata a eliminar.

### Verificado OK

- Instalación: `build-system` setuptools>=68, `requires-python >=3.10`, `dependencies = []`, entry point importable (`from src.email.cli import main` → ok).
- CLI: `python -m src.email --help` lista exactamente los comandos del README; `message`/`attachment`/`startup` validan sus subcomandos con los mismos nombres y aridades documentados (incl. frases literales `CONFIRMAR EXTRACCION`, `CONFIRMAR BORRADO PERMANENTE`, `CONFIRMAR BORRADO ADJUNTOS`, `CONFIRMAR ENVIO`).
- `src/email/__main__.py` delega en `cli_main` y propaga código de salida.
- CI cubre `compileall -q src` y `pytest -q` en matriz 3 OS × Python 3.10–3.13 (lo pedido: sí, con la salvedad M1).
- Secretos: sin coincidencias de credenciales hardcodeadas en `.json/.md/.toml/.yml`.
- Datos locales: `store/`, `work/`, `drafts/`, `contacts.json`, `build/`, `email_agent_cli.egg-info/` existen en disco pero están gitignored y sin trackear — el checkout limpio está limpio.
- Installers (`install.sh`/`install.ps1`) apuntan a `https://github.com/MauricioPerera/email-agent-kdd.git`, que coincide con `origin`; instalan vía `pip install git+URL` y exponen `email-agent` por consola.
- README menciona `SYNC_ATTACHMENT_BUDGET_MB` y aparece en la ayuda de `sync`.

## Cambios recomendados

1. Commit y push de los 41 `??` y 8 `M` antes de tagear (A1).
2. Unificar pytest: o borrar `pytest.ini` (pyproject ya tiene la sección, añadiendo ahí `python_files = frozen_*.py` y `addopts`), o completar `pytest.ini` con `testpaths` y borrar `[tool.pytest.ini_options]` (A2/B4).
3. Añadir en `ci.yml`: `python -m pip install .` + `email-agent --help`, y un job de empaquetado con `python -m build` y verificación del wheel en cada OS (M1, RELEASE.md pasos 4 y 6).
4. Mover la documentación de provider/constantes internas fuera de README a `docs/` (M3).
5. Reubicar los informes de sprint bajo `docs/` (B3) y limpiar excepciones de `.gitignore` y `tests/` vacío (B2/B5).

## Criterio de aceptación

- [ ] `git status` limpio (0 modificados, 0 sin trackear) tras el commit de A1.
- [ ] `pip install .` en un venv limpio y `email-agent --help` funcional en Windows, macOS y Linux.
- [ ] Existe exactamente una fuente de configuración pytest y `python -m pytest -q` recolecta solo `outputs/email-agent-kdd/tests` (sin barrer `work/` ni directorios locales).
- [ ] CI verde en matriz completa, incluyendo `compileall`, `pytest`, `pip install .` + `--help`, y `python -m build`.
- [ ] `git ls-files` sin entradas bajo `store/`, `work/`, `drafts/`, `.email-agent/`, `build/`, `*egg-info*` ni archivos tipo credencial.
- [ ] Sin secretos: sin coincidencias de patrones de credenciales en el tree trackeado.
- [ ] Comandos de README (`sync --attachments`, `attachment list/download/gc`, `startup install/status/remove`, `message delete/trash/restore/purge/remote-*`, `watch`, `draft`/`send`) presentes en la ayuda de la CLI con las frases de confirmación documentadas.