# Sprint 3 — Reporte `email-agent attachment list ROOT REL_PATH`

## Alcance implementado

Solo el comando de listado del diseño de adjuntos (`SPRINT3-ATTACHMENT-DESIGN.md`, sección "API / CLI"): `email-agent attachment list ROOT REL_PATH`. No se implementó `download` ni `gc`; no hay red ni IMAP; no hay commit/push.

## Cambios

- `src/email/cli.py`
  - Nuevo `_run_attachment(argv)`: valida la única acción admitida (`list`) y la aridad exacta `attachment list ROOT REL_PATH`; delega en `list_node_attachments` (`src/email/attachments.py`, API ya existente); imprime una línea JSON por adjunto con `sort_keys=True` (salida estable).
  - Mapeo de errores: `ValueError` (raiz o `REL_PATH` insegura — misma política de `read`) → código `2`; `FileNotFoundError`/`OSError`/cualquier otro fallo (nodo inexistente o E/S) → código `1`. Mensajes de stderr genéricos: sin rutas absolutas de ROOT, sin filename crudo, sin secretos, sin tracebacks.
  - `USAGE`, `--help` y el mensaje de subcomando inválido documentan `attachment list ROOT REL_PATH`. Docstring del módulo actualizado.
- `outputs/email-agent-kdd/tests/frozen_cli_attachments_list.py` (nuevo oracle, offline): store falso en `tmp_path` con nodos `.md` escritos a mano; sin directorio `attachments/` y sin red.
- `plugins/email-agent/skills/email-agent/SKILL.md` y `README.md`: documentación solo para esta sintaxis, con la política intacta (metadatos hoy; extracción solo con autorización explícita).

## Semántica del estado `stored|not-stored`

El estado proviene **exclusivamente del frontmatter** (`stored: true/false` por entrada o `attachments_stored:`), tal como produce `list_node_attachments`. El comando **nunca comprueba blobs en disco** ni conecta a IMAP; el oracle lo prueba con `stored: true` en un store sin directorio `attachments/`.

## Seguridad

- La resolución de `REL_PATH` queda delegada en `read_email_node` (`src/email/node.py`), que ya rechaza rutas absolutas, `~`, `\`, unidad Windows, componentes vacíos/`.`/`..` y escapado de la raíz → código `2`.
- `list_attachments` sanea el nombre (solo base, sin separadores ni caracteres de control, acotado a 80, fallback `attachment-<part_index>`); el filename crudo jamás compone rutas ni aparece en errores.

## Pruebas

- Nuevo: `frozen_cli_attachments_list.py` — 8 tests (formato nuevo, formato antiguo de solo hashes, nodo sin adjuntos, no-lectura-de-blobs, aridad/acción → 2, `REL_PATH` insegura → 2, nodo inexistente → 1 sin ruta absoluta, `--help` documenta la sintaxis).
- Relacionadas ejecutadas: `frozen_attachments.py`, `frozen_attachments_core.py`, `frozen_cli_remote_deletion.py` y los 8 `frozen_cli_*` de dispatch (query, search, read vía contact, accounts, account_setup, sync, sync_limit, send) — **182 tests, todos en verde** (65 + 117, sin solapamientos).

## Fuera de alcance (no tocado)

`attachment download`, `attachment gc`, extracción en `sync --attachments`, frase `CONFIRMAR EXTRACCION`, índice invertido, GC/ciclo `.trash` de blobs. Quedan pendientes de las preguntas abiertas del diseño.