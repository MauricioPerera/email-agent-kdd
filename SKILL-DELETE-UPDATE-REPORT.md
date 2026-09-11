# Reporte: actualización de SKILL.md con operaciones de borrado

## Resumen

Se actualizó `plugins/email-agent/skills/email-agent/SKILL.md` para documentar las operaciones de borrado ya implementadas en el CLI (`message delete/restore/trash/purge` sobre el store local y `message remote-delete/remote-restore/remote-purge` sobre IMAP). Se conservaron íntegros el frontmatter y todo el contenido previo; las dos secciones nuevas ("Message deletion (local store)" y "Message deletion (remote IMAP)") se insertaron antes de "Attachments".

Contenido de las secciones nuevas, según lo pedido:

- Comandos locales: `delete` (soft delete, predeterminado, mueve a `root/.trash` con manifiesto), `trash` (lista manifiestos), `restore`, y `purge` con la confirmación literal `CONFIRMAR BORRADO PERMANENTE`.
- Comandos remotos: `remote-delete` (copia a un mailbox Trash explícito + `UID STORE \Deleted` en el original; nunca `EXPUNGE` ni `close()`), `remote-restore` (devuelve de Trash al mailbox original, sin expunge), `remote-purge` (UID EXPUNGE selectivo de un solo UID, solo si el servidor anuncia UIDPLUS; si no, aborta antes de tocar el mailbox).
- Instrucciones para agentes: soft delete como predeterminado; nunca ejecutar `purge` ni completar `CONFIRMAR BORRADO PERMANENTE` por iniciativa propia; `remote-purge` solo con autorización explícita del usuario en la conversación; no pedir ni imprimir passwords ni referencias de credenciales; revisar resumen/cuenta/UID/mailbox antes de acciones destructivas; no reintentar operaciones de resultado incierto, reportar y esperar al usuario.

## Archivos tocados

- `plugins/email-agent/skills/email-agent/SKILL.md` — modificado (único archivo editado; frontmatter y contenido previo intactos).
- `SKILL-DELETE-UPDATE-REPORT.md` — creado (este reporte).

No se modificó ningún otro archivo y no se hizo commit.

## Validación

- Se verificó contra `src/email/cli.py` (ayuda y manejo de `message`: líneas 729–950) que los nombres de comandos y argumentos documentados coinciden: `delete ROOT REL_PATH`, `restore ROOT TRASH_REL_PATH`, `trash ROOT`, `purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE`, `remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX`, `remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX`, `remote-purge ROOT ACCOUNT_ID UID MAILBOX CONFIRMAR BORRADO PERMANENTE`.
- Se verificó contra `src/email/imap_deletion.py` el comportamiento descrito: `remote-delete` usa COPY a Trash explícito + `UID STORE \Deleted` sin `EXPUNGE` ni `close()`; `remote-purge` exige la confirmación exacta y `UIDPLUS` (capabilidad `_CAPABILITY = "UIDPLUS"`), y aborta antes de tocar el mailbox si el servidor no lo anuncia.
- El frontmatter (`name`, `description`) quedó sin cambios y las secciones existentes (Installation, Read and synchronize, Notifications, Search and inspect, Sending policy, Account management, Platform behavior) permanecen intactas.

## Estado

Completado. SKILL.md actualizado con la documentación de borrado; reporte escrito; sin cambios en otros archivos ni commit.