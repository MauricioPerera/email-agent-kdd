# SPRINT3 — Corrección del vínculo sync → attachment download

Fecha: 2026-09-11 · Estado: **LISTO** · Sin commit/push.

## Problema

`fetch_imap_messages` devuelve cada record con `imap_uid` pero sin `mailbox`, y
`_run_sync` no lo añadía antes de persistir. Resultado: el nodo sincronizado
quedaba sin identidad de re-descarga (`read_download_target` no podía recuperar
`account_id` + `imap_uid` + `mailbox`) y `attachment download` era inalcanzable
para todo lo que entraba por sync.

## Cambios

### `src/email/cli.py` (`_run_sync`)

- Import de `DEFAULT_MAILBOX` desde `src.email.imap_reader`.
- En la closure `fetch`, tras `fetch_imap_messages`, se estampa en cada record
  el **mailbox efectivo** de la sesión (`config.get("mailbox")` o `INBOX`)
  **antes de persistir**. No se guardan credenciales: el record solo gana la
  clave `mailbox` (str); `password`/`credential_ref` siguen fuera del nodo.
- Sin cambios en cursor, summary, contactos ni notificaciones.

### `src/email/persist.py` y `src/email/persist_at.py` (`_render`)

- Tras los campos fijos se emiten las líneas `imap_uid:` y `mailbox:`
  **solo cuando el record las trae con valor no vacío**.
- **Compatibilidad exacta**: un record legacy (sin esas claves) se renderiza
  byte a byte igual que antes — los oráculos congelados de
  `persist_email_okf` / `persist_email_okf_at` (comparación byte a byte contra
  el frozen-example y `delivered_to`) pasan intactos.
- Los nodos ya persistidos no se reescriben: `persist_email_okf_at` sigue
  rechazando destino existente con contenido distinto.

### Sin tocar

Lógica de download (`cli.py::_run_attachment_download`, `attachments.py`),
borrado (`imap_deletion.py`), envío ni documentación. `read_download_target`
ya leía `imap_uid`/`mailbox` del frontmatter; no requirió cambios.

## Prueba nueva (offline)

`outputs/email-agent-kdd/tests/frozen_sync_attachment_link.py` — sin red, sin
sockets, sin secretos reales (IMAP falsamente inyectado sobre
`imap_reader.imaplib.IMAP4_SSL`, credencial `env://` ficticia):

1. `sync` vía `cli_main` sobre un store temporal → el record con `imap_uid`
   termina en `store/emails/<raw_sha256>.md` con frontmatter
   `account_id: personal`, `imap_uid: 1`, `mailbox: INBOX`;
   `read_download_target` recupera la tripleta completa (nodo descargable) y
   `read_attachment_entries` ve el adjunto declarado.
2. Compatibilidad: un record legacy sin `imap_uid`/`mailbox` persiste igual que
   antes y `read_download_target` devuelve `imap_uid=None` (no descargable, por
   diseño).

## Verificación

```
python -m pytest outputs/email-agent-kdd/tests -q
671 passed in 3.03s
```

Incluye los 56 de sync/persist/download/list:
`frozen_sync_attachment_link`, `frozen_persist_email_okf`,
`frozen_persist_email_okf_at`, `frozen_cli_sync`,
`frozen_cli_attachments_download`, `frozen_cli_attachments_list`.

## Riesgo residual

`fetch_imap_messages` etiqueta `imap_uid` con el **número de secuencia** de la
sesión (id del `search`), no con el UID real de `UID SEARCH`. El vínculo queda
correcto y simétrico (el download re-fetchea por ese mismo identificador),
pero si en el futuro el re-fetch usa `UID FETCH`, ambos lados deben migrar
juntos. Fuera del alcance de esta corrección.