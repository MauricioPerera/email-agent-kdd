# Sprint 3 — Asociación OKF posterior a `attachment download` (reporte)

## Resumen

LISTO. Tras una extracción y copia exitosas, el nodo original se actualiza
**atómicamente** marcando `stored: true` **solo** en la entrada del `part_index`
descargado; todo lo demás (metadatos, otras entradas, cuerpo, `mailbox`,
`imap_uid`, `raw_sha256`) queda intacto byte a byte. Un nodo con formato legacy
de adjuntos (hashes sueltos) **no se reescribe silenciosamente**: error claro
antes de conectar y antes de escribir el DEST. Si la asociación falla hay
rollback sin corrupción: nodo intacto, sin `.tmp` residual y copia en DEST
retirada. La suite frozen completa queda en verde (**676 pruebas**; 5 nuevas).
Sin red, sin commit, sin push. IMAP, borrado y envío sin cambios.

## Archivos

- **Modificado:** `src/email/attachments.py` — tres primitivas nuevas:
  - `legacy_attachment_block(node_text)` — detección de solo lectura del formato
    antiguo (item de lista que no empieza por `sha256:`).
  - `mark_attachment_stored(node_text, part_index)` — reescribe únicamente la
    línea `stored:` de la entrada objetivo y conserva el resto del frontmatter y
    el cuerpo; rechaza con `legacy-node-format` y con `no-such-attachment`
    (errores nominales `AttachmentError`, mensajes saneados).
  - `write_node_text_atomic(root, rel_path, node_text)` — reescritura atomica
    `.tmp` + `os.replace` bajo ROOT, con la misma política de ruta relativa
    segura de lectura (relativa, `.md`, sin `..`/`~`/absolutas); ante fallo el
    nodo queda intacto y el `.tmp` se elimina.
- **Modificado:** `src/email/cli.py` (`_run_attachment_download` y sus imports) —
  1. Rechazo temprano (antes de cargar cuentas y conectar): nodo con bloque de
     adjuntos legacy → código `1`, mensaje "nodo legacy con formato antiguo de
     adjuntos (hashes sueltos)… re-sincronizar para reintentar".
  2. Después de la copia verificada en DEST: `mark_attachment_stored` +
     `write_node_text_atomic` (no-op si ya estaba `stored: true`).
  3. Rollback: si la asociación falla, el nodo queda intacto (escritura
     atómica), se retira la copia en DEST **solo si su contenido sigue siendo
     el payload verificado** (nunca borra datos ajenos) y se devuelve `1` con
     stdout vacío.
- **Nuevo:** `outputs/email-agent-kdd/tests/frozen_cli_attachment_association.py`
  — oráculo de la asociación (5 pruebas, IMAP falso inyectado sobre
  `imap_reader.imaplib.IMAP4_SSL`, store en `tmp_path`).

## Pruebas (5) y lo que fija cada una

1. **Marca solo el índice descargado y `attachment list` lo informa** — download
   del índice 1: el nodo cambia en **exactamente una línea** (`stored: false` →
   `stored: true`), que es la de la entrada con `part_index: 1`; cuerpo y demás
   frontmatter intactos; sin `.tmp` en todo ROOT; `attachment list` después
   reporta `["not-stored", "stored"]`; blob y copia en DEST re-verificados.
2. **Idempotencia de la asociación** — segunda descarga del mismo adjunto:
   `idempotent: true` y el nodo **no se reescribe** (idéntico byte a byte).
3. **Nodo legacy de hashes: error antes de conectar o escribir** — nodo con
   `imap_uid`/`account_id` pero entradas `- <hash>`: código `1`, mensaje claro,
   **cero llamadas al IMAP falso**, sin `attachments/`, sin copia en DEST y el
   nodo sin cambios.
4. **Rollback ante fallo de la asociación** — `write_node_text_atomic` parcheado
   para lanzar `OSError`: código `1`, stdout vacío, nodo intacto byte a byte,
   **ningún `.tmp` residual**, copia en DEST retirada, blob content-addressed
   verificado (no es corrupción) y `attachment list` sigue en `not-stored`.
5. **Conservación del frontmatter ajeno** — nodo con `mailbox`, `raw_sha256` y
   cuerpo: tras la descarga todos los fragmentos sobreviven, solo cambia la
   marca, y el nodo reescrito sigue siendo legible por la primitiva de lectura
   (`attachment list` → `stored`).

## Suite relacionada (en verde)

- `frozen_cli_attachments_download.py` (11), `frozen_cli_attachments_list.py` (9),
  `frozen_attachments.py`, `frozen_attachments_core.py`, y el resto de la suite
  frozen del proyecto: **676 passed** en `pytest outputs/email-agent-kdd/tests`.
- Nota de compatibilidad: el oráculo preexistente de download exige la palabra
  "legacy" en el error del nodo antiguo; el mensaje nuevo la incluye ("nodo
  legacy con formato antiguo de adjuntos (hashes sueltos)…").

## Fuera de alcance (sin cambios)

`imap_reader.py`, `imap_deletion.py`, `deletion.py`, `smtp_send.py`, sync,
persistencia OKF y los comandos `message`/`remote-*`. Sin red ni commit/push.