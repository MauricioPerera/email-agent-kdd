# SPRINT6 — Preparación del plugin

Fecha: 2026-09-11 · Alcance: `.codex-plugin/plugin.json`, `plugins/email-agent/skills/email-agent/SKILL.md`, `README.md`, `SECURITY.md`, `pyproject.toml`, `installers/`, `.agents/plugins/marketplace.json` y la CLI (`src/email/cli.py`). Sin red, sin commit, sin push, sin publicación.

## Sí/no

El plugin es ahora descubrible e instalable por un agente no técnico: faltaba validar el manifiesto (que existía en HEAD pero no se audito), el prefijo de la ayuda de la CLI estaba mal (`email-cli` en vez de `email-agent`) y los instaladores no verificaban nada tras instalar. Todo corregido y verificado; suite completa verde (724 passed).

## Auditoría previa

- **`plugins/email-agent/.codex-plugin/plugin.json` existía** (trackeado en HEAD con cambios sin commit). Mi primera pasada lo sobrescribió perdiendo `longDescription` y `capabilities`; ambos restaurados. Estado final: metadatos ampliados (repository, license MIT, keywords), `skills: ["./skills"]` (rutas válidas para el spec de plugins), `interface.longDescription/capabilities` conservados, `defaultPrompt` en forma de lista (≤ 3, cada una ≤ 128 chars), `author`/`developerName` reales.
- **`SKILL.md`: sin cambios necesarios.** Verificado comando a comando contra `src/email/cli.py` (líneas 1356–1424 + `USAGE`): `account setup|setup-gui|list|remove`, `sync [--attachments]`, `watch`, `query/search/read`, `notification add|list|delete`, `message delete|trash|restore|purge|remote-delete|remote-restore|remote-purge`, `attachment list|download|gc`, `startup install|status|remove`, `draft`, `send`. Las 5 frases literales de confirmación están presentes y exactas. El frontmatter (name/description) es válido.
- **`README.md` / `SECURITY.md` / `pyproject.toml`: coherentes** con la CLI (entry point `email-agent = "src.email.cli:main"`, `requires-python >= 3.10`, `dependencies = []`); solo añadidos de plugin en README (abajo).
- **`.agents/plugins/marketplace.json`: correcto** — apunta a `./plugins/email-agent`, que ahora contiene su manifiesto.

## Cambios

| Archivo | Cambio |
|---|---|
| `plugins/email-agent/.codex-plugin/plugin.json` | Metadatos de descubrimiento (repository/license/keywords), `skills` como lista de rutas validables, prompts por defecto; conservados `longDescription` y `capabilities` de HEAD |
| `src/email/cli.py` | Prefijo de `USAGE`/`SYNC_USAGE`/`WATCH_USAGE` renombrado `email-cli` → `email-agent` (26 sustituciones, solo strings de ayuda; verificado que ningún test dependía de él) |
| `installers/install.ps1` / `install.sh` | Post-instalación ejecutan `email-agent --help`, fallan con aviso de PATH si no responde; mensaje final "instalado y verificado" |
| `README.md` | Nueva sección "Instalación como plugin (para agentes)": comandos de instalación con verificación, rutas del manifiesto/catálogo, comando de validación reproducible y las 5 frases de confirmación que el usuario siempre escribe |
| `docs/RELEASE.md` | El listado de CI menciona la validación del plugin vía `frozen_plugin_manifest.py` |
| `outputs/email-agent-kdd/tests/frozen_plugin_manifest.py` | NUEVO: oráculo congelado, 12 checks |

## Prueba reproducible

```bash
python outputs/email-agent-kdd/tests/frozen_plugin_manifest.py
# OK frozen_plugin_manifest (12 checks)
python -m pytest -q                 # 724 passed (incluye los 12 del manifiesto)
python -m src.email --help          # usage: email-agent ... (prefijo corregido)
sh -n installers/install.sh         # sintaxis OK
```

Cobertura del oráculo (sin ejecutar la CLI ni red):

1. `plugin.json` existe, JSON válido, name/version semver/description/license.
2. Rutas de `skills` relativas con `./`, sin `..`, resuelven dentro del plugin.
3. `apps`/`mcpServers` solo declarados si el archivo `.app.json`/`.mcp.json` existe.
4. Frontmatter de `SKILL.md` (name/description).
5. `marketplace.json` apunta a un directorio de plugin existente.
6. Los 27 comandos documentados en SKILL.md existen en la fuente de la CLI.
7. El prefijo de ayuda es `email-agent` y ya no existe `email-cli` en la CLI.
8. Las 5 frases de confirmación están en la CLI y documentadas en SKILL.md.
9. Los dos instaladores ejecutan `email-agent --help` tras instalar.
10. Los instaladores apuntan al repositorio de origin.
11. `pyproject.toml` declara el entry point, Python >= 3.10 y cero dependencias.

## Resultados

- Oráculo standalone: `OK (12 checks)`, exit 0.
- `python -m pytest -q`: **724 passed** (12 seleccionables con `-k plugin_manifest`, verificado).
- `python -m src.email --help`: exit 0, uso con prefijo `email-agent`.
- `email-agent --help` del script instalado: no ejecutable en esta máquina porque `email-agent-cli` no está instalado como paquete regular (solo `egg-info` local); el smoke real lo hace CI con `pip install .` (paso 3 del pipeline).

## Limitaciones

- No se añadieron `hooks`/`mcpServers`/`apps` al manifiesto: no existen `.mcp.json` ni `.app.json` en el plugin y declararlos sin archivo rompe la validación.
- La verificación del entry point instalado no corre en esta máquina (instalación editable local); el smoke `pip install .` + `email-agent --help` está en CI en los 3 OS.
- Pendiente de la decisión del propietario (fuera de alcance): commit/push de los ~50 archivos sin commit, incluidos este reporte y los tests congelados de los sprints 1–5. No se hizo commit ni push por instrucción.