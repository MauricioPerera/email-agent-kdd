# Reporte: ImapDeletionProvider (borrado remoto IMAP)

Fecha: 2026-09-10
Archivos creados/modificados:

- `src/email/imap_deletion.py` (implementación)
- `outputs/email-agent-kdd/tests/frozen_imap_deletion.py` (tests congelados)

Ningún otro archivo fue modificado.

## Alcance pedido vs. entregado

| Requisito | Estado |
| --- | --- |
| `ImapDeletionProvider` con `connection_factory` inyectable (default `imaplib.IMAP4_SSL`) | OK |
| `soft_delete(account, config, uid, trash_mailbox)`: login → select mailbox (escritura, `readonly=False`) → `UID COPY <uid> <trash>` → `UID STORE <uid> +FLAGS (\Deleted)` | OK |
| `soft_delete` NUNCA llama EXPUNGE ni `close()` (close expurga en RFC 3501); libera con `unselect()` + `logout()` | OK |
| `restore(account, config, trash_mailbox, uid, original_mailbox)`: select Trash (escritura) → `UID COPY <uid> <original>` → `UID STORE <uid> +FLAGS (\Deleted)` en Trash, sin EXPUNGE | OK |
| `permanent_delete` exige la frase literal exacta `CONFIRMAR BORRADO PERMANENTE` | OK |
| `permanent_delete` solo llama `UID EXPUNGE` si `capabilities` contiene `UIDPLUS`; sin UIDPLUS falla antes de tocar el buzón (sin EXPUNGE, sin select) | OK |
| Validación: UID `int no bool >= 1`, mailbox str no vacío sin bordes, account (`account_id`, `email`) y config (`host`, `username`, `password`, `port`) — falla ANTES de abrir conexión | OK |
| Errores sanitizados: la password nunca aparece en los mensajes (se reemplaza por `***`); fallo envuelto en `RuntimeError` con `account_id` + `host` | OK |
| Conexión liberada en `finally` (unselect + logout tolerantes) incluso ante fallos | OK |

Nota sobre el mailbox origen de `soft_delete`: la firma pedida no incluye
mailbox; se toma `config.get("mailbox")` con default `"INBOX"`.

## API

```python
class ImapDeletionProvider:
    def __init__(self, connection_factory=None)
    def soft_delete(self, account, config, uid, trash_mailbox) -> dict
    def restore(self, account, config, trash_mailbox, uid, original_mailbox) -> dict
    def permanent_delete(self, account, config, mailbox, uid, confirmation) -> dict
```

- `MailDeletionProvider` es un `Protocol` runtime-checkable (igual que
  `EmailProvider`); `ImapDeletionProvider` lo satisface.
- Wrappers de conveniencia: `imap_soft_delete`, `imap_restore`,
  `imap_permanent_delete` (aceptan `connection_factory=None`).
- Recibos (dicts serializables) con `action`, `account_id`, `mailbox`/
  `trash_mailbox`/`original_mailbox`, `uid`, `copied`, `flagged_deleted`,
  `expunged` (y `uidplus` en el purge).

## Decisiones de seguridad

1. `unselect()` en vez de `close()`: en RFC 3501 `close()` expurga
   silenciosamente los mensajes `\Deleted`, lo que rompería la reversibilidad.
2. Trash es un parámetro explícito en `soft_delete` (sin autodetección LIST,
   que era ambigua con múltiples carpetas tipo Trash).
3. El purge con confirmación inválida ni siquiera abre conexión
   (la frase se valida antes de la factory).
4. El purge sin UIDPLUS aborta tras login, ANTES de `select`: un `EXPUNGE`
   sin UID expurgaría todo el buzón.
5. `uid` rechaza `bool` (`True` es instancia de `int`).

## Tests (fake IMAP, sin red ni credenciales reales)

`FakeIMAP` en memoria registra cada llamada; el provider se inyecta con
`connection_factory=lambda host, port: fake`.

11 tests, todos verdes:

1. `test_imap_provider_satisfies_protocol` — conformidad estructural.
2. `test_soft_delete_copies_flags_deleted_and_never_expunges` — login, select
   en escritura, `UID COPY 5 INBOX.Trash`, `UID STORE 5 +FLAGS (\Deleted)`,
   cero EXPUNGE, cero `close`, unselect+logout, recibo exacto.
3. `test_soft_delete_rejects_invalid_uid_and_trash_without_touching_server`
   — uid `0/-1/"5"/True` y trash `""/"  …"/None` → `ValueError` sin abrir
   conexión (0 llamadas al fake).
4. `test_restore_moves_from_trash_to_original_without_expunge` — select
   Trash en escritura, COPY al original, STORE `\Deleted` en Trash, sin
   EXPUNGE.
5. `test_restore_rejects_same_mailbox_without_connecting` — origen == destino
   → `RuntimeError` sin conexión.
6. `test_purge_without_exact_confirmation_never_touches_the_server` — 6 frases
   incorrectas → `ValueError`, el fake queda con **cero** llamadas.
7. `test_purge_without_uidplus_fails_and_never_expunges` — capabilities sin
   UIDPLUS → `RuntimeError`, sin EXPUNGE y sin `select` (aborta antes del
   buzón).
8. `test_purge_confirmed_with_uidplus_uses_uid_expunge` — `UID EXPUNGE 5`
   selectivo + recibo con `uidplus: True`.
9. `test_purge_only_expunges_the_requested_uid` — exactamente un EXPUNGE, el
   uid pedido.
10. `test_connection_is_released_and_password_is_never_exposed` — login roto:
    el error menciona `account_id`+`host` pero nunca la password; logout igual
    se ejecuta.
11. `test_missing_account_or_config_fields_fail_before_connecting` — account/
    config incompletos y mailbox/trash vacíos → `ValueError` con el fake sin
    tocar.

## Ejecución

```
$ python -m pytest outputs/email-agent-kdd/tests/frozen_imap_deletion.py -q
11 passed in 0.28s
```

Solo se corrió ese archivo. Sin red, sin credenciales reales, sin commit.