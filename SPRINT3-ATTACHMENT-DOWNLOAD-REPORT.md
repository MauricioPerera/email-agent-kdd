# Sprint 3 — Verificación de `attachment download` (reporte)

## Resumen

LISTO. Verificación completada **sin modificar código de producción**. Se creó el
oráculo `frozen_cli_attachments_download.py` (11 pruebas, todas en verde) que cubre
la extracción autorizada de adjuntos end-to-end contra un IMAP falso (sin red, sin
sockets, sin credenciales reales). Las pruebas relacionadas de attachments
(core, list) y de persistencia siguen en verde (71 pruebas). Sin commit ni push.

## Archivos

- **Nuevo:** `outputs/email-agent-kdd/tests/frozen_cli_attachments_download.py`
  — oráculo del comando `attachment download ROOT REL_PATH INDEX DEST
  CONFIRMAR EXTRACCION` con fabrica IMAP falsa inyectada por monkeypatch sobre
  `imap_reader.imaplib.IMAP4_SSL` (la fabrica real de producción no cambia) y
  store temporal en `tmp_path` (cuenta `env://` + `mail-servers.json` + nodos
  `.md` escritos a mano con `account_id`/`imap_uid`/`mailbox`).
- **Solo lectura** (no modificados): `SPRINT3-ATTACHMENT-DESIGN.md`,
  `src/email/attachments.py`, `src/email/imap_reader.py`, `src/email/cli.py`
  (secciones `_run_attachment_download` / `_run_attachment`),
  `src/email/persist.py`, `src/email/persist_at.py`.

## Pruebas (11) y lo que fija cada una

1. **Confirmación antes de conectar/escribir** — frase ausente → `2`; frases
   incorrectas (`CONFIRMAR`, minúsculas, `...EXTRA`, doble espacio, todo en un
   token) → `1` con **cero llamadas al IMAP falso**, sin `attachments/` y sin
   escribir el DEST. La frase literal como un solo argumento válido se acepta
   (semántica de `" ".join` del CLI, verificada implícitamente en los casos de
   éxito).
2. **Éxito: solo el índice MIME pedido** — mensaje con 3 adjuntos; download
   índice 1 → receipt JSON con `sha256/size/display/blob/dest/idempotent:false`,
   blob content-addressed en `ROOT/attachments/ab/cd/<sha>` dentro de ROOT,
   DEST verificado byte a byte, **no** se crea el blob del índice 0; la recorrida
   real queda registrada: `connect(imap.saved.test:1143)`, `login` con la
   credencial resuelta en memoria, `select(INBOX, readonly=True)`,
   `fetch("7", "(RFC822)")`; sin secretos ni rutas absolutas en la salida.
3. **Mailbox del nodo** — `mailbox: INBOX/Sub` del frontmatter manda sobre el
   default; `select` siempre `readonly=True`.
4. **Nodo legacy rechazado** — sin `account_id` y sin `imap_uid` (formato antiguo,
   solo hashes) → `1` con mensaje "legacy", sin conexión ni escritura; también
   con `account_id` pero sin `imap_uid`.
5. **DEST traversal/absoluta → `2` sin conectar** — `../fuga.pdf`,
   `salidas/../../fuga.pdf`, `C:/Windows/fuga.pdf`, `/tmp/...`, `~/...`: nada se
   conecta y no aparece ningún archivo fuera ni dentro de ROOT.
6. **Tipo bloqueado y tamaño límite** — `application/x-msdownload`, extensión
   `.js` con MIME inocente, y `size` declarado > 25 MB: todos `1` **antes** de
   conectar; sin blob, sin DEST.
7. **Hash mismatch sin sobrescribir** — blob preexistente corrupto (mismo hash
   declarado, otro contenido) → `hash-mismatch`, el blob queda byte a byte
   intacto, sin `.tmp` residual y sin copia en DEST; sha declarado distinto del
   contenido descargado → `hash-mismatch` sin escribir nada.
8. **Idempotencia** — segunda descarga del mismo adjunto → exit 0,
   `idempotent: true`, blob idéntico, un solo `.meta` (no se duplica), DEST
   re-verificado.
9. **Error IMAP sanitizado** — fallo en `fetch` y en `login` con la password en
   el mensaje → `1`, stdout vacío, sin password, sin host del servidor, sin rutas
   absolutas, sin traceback; nada escrito.
10. **Cuenta/credencial ausente → `1` sin conectar** — `account_id` fantasma
    ("cuenta no encontrada") y env var borrada ("credencial irresoluble", sin
    exponer `credential_ref`).
11. **Aridad e INDEX inválidos** — índices `x`, `-1`, `1.5`, `99` (inexistente) y
    nodo inexistente → `1`/`2`, sin conexión, sin tracebacks.

## Ejecución

- `frozen_cli_attachments_download.py`: **11 passed**.
- Relacionadas: `frozen_attachments.py` + `frozen_attachments_core.py` +
  `frozen_cli_attachments_list.py` + `frozen_persist_email_okf.py` +
  `frozen_persist_email_okf_at.py` → **71 passed** (total 82, 0 fallos).

## Estado

- Cobertura del diseño (sección "API / CLI" y "Pruebas offline" del
  SPRINT3-ATTACHMENT-DESIGN.md): casos 1 (confirmación), 2 (índice pedido),
  3 (hash verificado / sin sobrescritura), 4 (límites), 5 (tipos prohibidos),
  6 (idempotencia) y 9 (sanitización de errores) verificados a nivel CLI.
- Sin red, sin secretos reales, sin commit/push, sin cambios de producción.

## Pendiente (fuera del alcance de esta verificación)

- `sync --attachments` (extracción masiva con presupuesto) no tiene oráculo
  todavía.
- GC / conteo de referencias del `.meta` (`refs: 0`) y ciclo `.trash` para blobs:
  pendiente de decisión (preguntas 3 del diseño).
- El nodo sincronizado hoy no persiste `imap_uid` en frontmatter (`persist.py` no
  lo emite), así que todo nodo real sigue siendo "legacy" para `download` hasta
  que sync lo escriba — el oráculo ya documenta el contrato esperado.