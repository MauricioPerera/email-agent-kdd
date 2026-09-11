# Sprint 7 — Validación oficial del plugin (plugin.json)

## Objetivo
Corregir `plugins/email-agent/.codex-plugin/plugin.json` para pasar el validador oficial
`C:\Users\Administrador\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py`
sin perder información útil, manteniendo coherentes
`.agents/plugins/marketplace.json`, `skills/email-agent/SKILL.md` y
`outputs/email-agent-kdd/tests/frozen_plugin_manifest.py`.

## Diagnóstico (errores previos del validador)
1. `longDescription` en el nivel raíz → campo no aceptado (el esquema oficial solo
   permite `id, name, version, description, skills, apps, mcpServers, interface,
   author, homepage, repository, license, keywords`).
2. `skills: ["./skills"]` (array) → el validador exige un string cuya ruta
   normalizada resuelva exactamente a `skills`.
3. `interface.longDescription` ausente (estaba en la raíz) → debe ser string no vacío.

## Cambios

### `plugins/email-agent/.codex-plugin/plugin.json`
- Eliminado `longDescription` del nivel raíz; su texto se movió íntegro a
  `interface.longDescription` (donde el esquema lo acepta y lo exige).
- `skills` convertido de lista `[\"./skills\"]` a string `\"./skills\"`. La forma
  string pasa el validador oficial y sigue cumpliendo la prueba frozen
  (`test_manifest_component_paths_are_relative_and_resolve` exige prefijo `./`,
  ruta relativa y que resuelva dentro del plugin).
- `interface.capabilities` rellenado de `[]` a 6 entradas de texto (sincronización
  paginada read-only, search/query, ciclo trash/restore/borrado permanente,
  adjuntos, watchers/notificaciones, envío y borrado gated) para conservar el
  detalle descriptivo antes en `longDescription`.

### Sin cambios (revisados, coherentes)
- `.agents/plugins/marketplace.json`: la entrada `email-agent` apunta a
  `./plugins/email-agent`, que existe — sigue válida.
- `skills/email-agent/SKILL.md`: frontmatter `name`/`description` válidos y
  comandos presentes en la CLI (verificado por el validador y por la prueba
  frozen, ambos en verde).
- `outputs/email-agent-kdd/tests/frozen_plugin_manifest.py`: no requirió
  modificación; acepta `skills` como string con prefijo `./`.

## Verificación
| Comando | Resultado |
| --- | --- |
| `python C:\Users\Administrador\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\email-agent` | `Plugin validation passed` |
| `python outputs/email-agent-kdd/tests/frozen_plugin_manifest.py` | `OK frozen_plugin_manifest (12 checks)` |
| `python -m pytest -q` | `724 passed in 4.17s` |

## Notas
- Sin commit ni push; sin publicación; sin exposición de secretos.
- Los archivos del repo permanecen sin commit (estado de trabajo igual al resto del sprint).