# Publicación

Proceso de release. La publicación pública del repositorio requiere una decisión explícita del propietario; este documento no la ejecuta.

## Qué valida CI automáticamente

`.github/workflows/ci.yml` (matriz Windows/macOS/Linux × Python 3.10–3.13) ejecuta en cada combinación:

1. `python -m compileall -q src`
2. `python -m pytest -q` (config única en `pytest.ini`: `python_files = frozen_*.py`, `testpaths = outputs/email-agent-kdd/tests`) — incluye `frozen_plugin_manifest.py`, que valida el manifiesto del plugin (`plugins/email-agent/.codex-plugin/plugin.json`), el catálogo (`.agents/plugins/marketplace.json`), el SKILL.md y las frases de confirmación literales de la CLI
3. `pip install .` + `email-agent --help` (smoke del entry point, paso 6 automatizado)
4. `python -m build` en un job separado de empaquetado (sdist + wheel, verificados y **sin publicar artefactos**)
5. Instalación sin índice de los wheels de la release y sus dependencias en un
   venv vacío mediante `.github/ci/offline_install_smoke.py` (matriz completa).

Además un job de higiene falla el build si `git ls-files` contiene `store/`, `work/`, `drafts/`, `.email-agent/`, `build/`, `*.egg-info`, o archivos de secretos (`.env`, `*.key`, `*.pem`, `credentials*.json`, etc.); solo informa patrón y conteo, nunca rutas ni contenido sensible.

## Checklist de release

### 1. Pre-commit (local)

- [ ] `python -m pytest -q` verde (suite completa) y `python -m compileall -q src` sin errores.
- [ ] `python -m build` produce sdist y wheel sin errores; el wheel instalado en un entorno aislado responde a `email-agent --help`.
- [ ] Sin datos locales trackeados: nada bajo `.email-agent/`, `store/`, `drafts/` o `work/` en el árbol (el job de higiene es la red de seguridad, no un sustituto de esta revisión).
- [ ] Sin secretos en el árbol ni en `git diff` (contraseñas, tokens, `credential_ref`).

### 2. Coherencia de versión y manifiestos

- [ ] Versión idéntica en `pyproject.toml` (`email-agent-cli`), en `plugins/email-agent/.codex-plugin/plugin.json` y en la entrada nueva de `CHANGELOG.md` (semver estricto, lo valida `frozen_plugin_manifest.py`).
- [ ] `CHANGELOG.md` actualizado con una entrada por versión (formato Keep a Changelog), incluyendo limitaciones conocidas y migraciones de esa versión.
- [ ] Manifiesto del plugin validado (`python -m pytest -q` lo hace vía `frozen_plugin_manifest.py`); `longDescription`/`capabilities` dentro de `interface`, `defaultPrompt` como lista (≤ 3 entradas, ≤ 128 caracteres).
- [ ] `.agents/plugins/marketplace.json` apunta a `MauricioPerera/email-agent-kdd`, ref `v0.2.0`, ruta `plugins/email-agent`.

### 3. Documentación fiel a las funciones actuales (sprints 1–10)

- [ ] README, SKILL.md y CHANGELOG documentan todos los comandos reales de la CLI: `query`, `search`, `read`, `account setup|setup-gui|add|remove|list`, `contact list|show|find`, `sync [--attachments]`, `watch`, `notification add|list|show|delete`, `startup install|status|remove`, `message delete|trash|restore|purge|remote-delete|remote-restore|remote-purge`, `attachment list|download|gc`, `draft`, `draft show`, `send` (verificar contra la salida de `email-agent --help`).
- [ ] Las cinco frases literales de confirmación aparecen exactas y se declara que las escribe el usuario, nunca el agente: `CONFIRMAR ENVIO`, `CONFIRMAR DESVINCULAR`, `CONFIRMAR BORRADO PERMANENTE` (local y remoto), `CONFIRMAR BORRADO ADJUNTOS`, `CONFIRMAR EXTRACCION`.
- [ ] Documentados los tres almacenes de credenciales nativos (Windows Credential Manager, macOS Keychain vía `security`, Linux Secret Service/libsecret vía `secret-tool`) y la inexistencia de fallback menos seguro.
- [ ] Documentadas las limitaciones conocidas: Python 3.10+ (CI valida 3.10–3.13; 3.14 sin testar), tkinter necesario para `setup-gui`, Secret Service necesita sesión de escritorio, `remote-purge` solo con `UIDPLUS`, `TRASH_MAILBOX` obligatorio y explícito, límites de adjuntos (25 MB por adjunto, presupuesto por sync de 100 MB con `SYNC_ATTACHMENT_BUDGET_MB`, tipos/extensiones bloqueados), nodos legacy rechazados en `attachment download` (re-sincronizar como vía de migración), `watch` con mínimo de 30 s.
- [ ] SECURITY.md describe la desvinculación transaccional (`account remove`), la precomprobación IMAP/SMTP que jamás envía correo, y que los mensajes de error no exponen secretos ni tracebacks.

### 4. Publicación

- [ ] Hacer commit y push de todos los cambios (CI valida lo que está en `origin`, no el disco local).
- [ ] Confirmar el propietario y la licencia.
- [ ] Publicar un tag semántico (p. ej. `v0.2.0`) y hashes de los artefactos.
- [ ] Adjuntar también `pypdf-6.18.1-py3-none-any.whl` con su licencia incluida;
  incluir `typing_extensions-4.16.0-py3-none-any.whl` para Python 3.10 y su licencia;
  agregar sus hashes a `SHA256SUMS.txt` y probar instalación sin índice en un venv vacío.
- [ ] Publicar el plugin y apuntar su marketplace a la release estable.
- [ ] Publicar los instaladores (`installers/install.ps1`, `installers/install.sh`) solo si cambia el repositorio de distribución; ambos ya verifican `email-agent --help` tras instalar.
