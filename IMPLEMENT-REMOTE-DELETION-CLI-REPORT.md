# Reporte: integración de `imap_deletion.py` en la CLI (`message remote-*`)

Fecha: 2026-09-10
Archivos modificados/creados:

- `src/email/cli.py` (integración: comandos `message remote-delete`, `remote-restore`, `remote-purge`)
- `outputs/email-agent-kdd/tests/frozen_cli_remote_deletion.py` (tests nuevos de dispatch)
- `README.md` (documentación actualizada)
- `IMPLEMENT-REMOTE-DELETION-CLI-REPORT.md` (este reporte)

NO se modificó `src/email/imap_deletion.py` ni ningún comando existente
(`query`, `search`, `read`, `account`, `contact`, `sync`, `watch`,
`notification`, `startup`, `draft`, `send`, y `message delete/restore/trash/purge`
locales). Sin red, sin credenciales reales, sin commit.

## Comandos integrados (orden pedido)

```text
message remote-delete  ROOT ACCOUNT_ID UID TRASH_MAILBOX
message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX
message remote-purge   ROOT ACCOUNT_ID UID MAILBOX CONFIRMAR BORRADO PERMANENTE
```

En los tres: `UID` va inmediatamente tras `ACCOUNT_ID` y se valida como entero
positivo (`_parse_uid`); cualquier desviación de aridad o UID inválido devuelve
código `2` con usage en stderr, sin tocar el provider.

## Delegación y seguridad

- La cuenta guardada se carga con `account_store.load_email_accounts(root)` y
  su credencial con `credentials.resolve_credential(account["credential_ref"])`
  (solo `env://NAME` / `wincred://LABEL`). Jamás se acepta una password por
  argv ni se imprime en stdout/stderr o errores.
- Host y puerto: si existe `mail-servers.json` para la cuenta
  (`mail_server_store.load_mail_server_config`) se usan `imap_host`/`imap_port`
  guardados; si no, host por defecto del proveedor (`imap.gmail.com`,
  `outlook.office365.com`), sin puerto fijo (el provider usa 993).
- `remote-delete` → `ImapDeletionProvider.soft_delete(account, config, uid,
  trash_mailbox)`; `TRASH_MAILBOX` es parámetro explícito. El mailbox origen lo
  resuelve el provider (`INBOX` por defecto; el store de servidores guarda solo
  host/puerto — limitación documentada).
- `remote-restore` → `provider.restore(account, config, trash_mailbox, uid,
  original_mailbox)`, sin expunge.
- `remote-purge` → `provider.permanent_delete(account, config, mailbox, uid,
  _PURGE_CONFIRMATION)`. La CLI exige la frase literal exacta
  `CONFIRMAR BORRADO PERMANENTE` (también aceptada concatenada en un argumento)
  ANTES de instanciar/llamar al provider; el provider además exige UIDPLUS.
- Errores: `ValueError` del provider → `1` ("operación remota falló"); cualquier
  otro fallo → `1` ("operación IMAP falló (sin cambios seguros)"); sin
  tracebacks ni contenido crudo de excepciones. Éxito → recibo JSON del
  provider en stdout, una línea, código `0`.
- Ayuda (`--help`, usage de `_run_message`) actualizada con el nuevo orden.

## Tests (13 nuevos, sin red real)

`frozen_cli_remote_deletion.py`: provider falso (`_FakeProvider`) inyectado con
`monkeypatch.setattr(cli, "ImapDeletionProvider", ...)`; cuentas y servidores
escritos con los stores reales en `tmp_path`; credencial vía `env://` +
`monkeypatch.setenv`. Cubre:

1. Orden exacto de los argumentos hacia `soft_delete` / `restore` /
   `permanent_delete` y recibo JSON en stdout (código 0).
2. Prioridad de host/puerto guardados; host por defecto (gmail/outlook) sin
   config guardada y ausencia de `port` en ese caso.
3. `remote-purge`: frase literal exacta (rechaza minúsculas, frase cortada,
   texto extra y doble espacio); sin frase exacta el provider jamás se llama.
4. Aridad y UID inválidos → `2` (con usage), provider intacto.
5. Cuenta ausente / credencial ausente → `1`, provider intacto, sin filtrar
   `credential_ref` ni el secreto.
6. `ValueError` y `RuntimeError` del provider → `1`, sin traceback; la password
   inyectada en el mensaje de error nunca aparece en stderr.
7. `--help` documenta los tres comandos con el orden pedido.

## Resultados

- Tests nuevos: 13 passed.
- Suite completa (`outputs/email-agent-kdd/tests`): 558 passed, 0 failed.
- Sin red, sin credenciales reales, sin commit (pendiente de decisión del usuario).