---
task: cli_account_remove
intent: desvincular una cuenta de forma transaccional borrando el secreto al final
target: src/email/unlink.py + src/email/cli.py
signature: "def unlink_email_account(root: str, account_id: str, credential=None, servers=None) -> dict"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_account_remove.py
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_cli_account_remove.py outputs/email-agent-kdd/tests/frozen_account_unlink_stubs.py -q"
deps_allowed: [json, os, pathlib, re, sys]
forbids: [eval, exec, subprocess, network_access, getpass]
---
## Intent
Desvincular una cuenta local de correo de forma transaccional: tras la confirmacion literal del usuario `CONFIRMAR DESVINCULAR`, limpiar la referencia de la cuenta en `accounts.json`, su configuracion publica de servidores en `mail-servers.json` y, al final, el secreto del almacen nativo correspondiente, sin tocar los correos descargados y sin exponer secretos.

## Interface
`def unlink_email_account(root: str, account_id: str, credential=None, servers=None) -> dict` en `src/email/unlink.py`. `credential` (default `src.email.credentials.delete_stored_credential`) y `servers` (default `src.email.mail_server_store.remove_mail_server_config`) son los unicos puntos de inyeccion para pruebas offline.

`src/email/cli.py::_account_remove(argv)` delega todo el estado en `unlink_email_account(argv[2], argv[3])` y mantiene la confirmacion literal como primera comprobacion (antes de leer disco).

Orden transaccional obligatorio:

1. Validar `account_id` (`ValueError` si no es `str` no vacio).
2. Pre-lecturas sin mutar: `load_email_accounts(root)` y buscar el registro por `account_id` (ausente -> `LookupError("cuenta no encontrada")`); capturar el registro completo y `snapshot = load_mail_server_config(root, account_id)` (puede ser `None`).
3. `servers(root, account_id)`: limpiar la config publica de servidores.
4. `remove_email_account(root, account_id)`: commit de la referencia local.
5. `credential(record["credential_ref"])` AL FINAL: borrar el secreto del almacen nativo. Los backends reales (`wincred://`, `keychain://`, `secretservice://`) tratan "ausente" como ya desvinculado; `env://` no persiste nada.

## Invariants

- El secreto del almacen nativo SOLO se borra cuando todo lo local ya quedo limpio; jamas al reves.
- El rollback es best-effort y re-lanza el error ORIGINAL: si el fallo ocurre en los pasos 3 o 4, se repone `mail-servers.json` desde `snapshot` (si no era `None`); si ocurre en el paso 5, se repone `save_email_account(root, record)` y la config de servidores si `snapshot` no era `None`. Si el propio rollback falla, se conserva el error original (nunca se enmascara).
- El secreto NUNCA se resuelve ni se lee durante la desvinculacion: `resolve_credential` no se llama y el valor del secreto no circula por la funcion.
- El resultado jamas incluye `credential_ref` ni ningun secreto: solo `{"account_id", "email", "status": "unlinked"}`.
- Los correos descargados bajo el root se preservan byte a byte: la desvinculacion no borra ni reescribe archivos de mensajes ni indices de adjuntos.
- Un secreto ausente no es un error: el unlink termina en exito.
- Los mensajes de error son genericos, sin secretos, sin `credential_ref` ni tracebacks.
- Ante confirmacion incorrecta no se lee disco ni se invoca ningun stub: nada cambia.
- Sin red, sin subprocess, sin `eval`/`exec`; determinista.

## Examples

- `unlink_email_account(root, "personal")` con cuenta `wincred://label` existente -> elimina la entrada de `mail-servers.json` (si la habia), quita el registro de `accounts.json`, borra el secreto al final y devuelve `{"account_id": "personal", "email": "...", "status": "unlinked"}`; los correos siguen intactos.
- `unlink_email_account(root, "fantasma")` -> `LookupError` y ningun cambio.
- `unlink_email_account(root, "  ")` -> `ValueError`.
- `credential` que lanza `RuntimeError` -> `accounts.json` y `mail-servers.json` vuelven al estado previo y el error se propaga.
- CLI: `["account", "remove", ROOT, ID, "CONFIRMAR", "DESVINCULAR"]` -> imprime `{"account_id": ID, "status": "unlinked"}` y retorna `0`.
- CLI: confirmacion `"DESVINCULAR"` sola o `"CONFIRMAR BORRAR"` -> `error: confirmacion explicita requerida para desvincular` en stderr, retorna `1`, nada cambia.
- CLI: cuenta inexistente -> `error: cuenta no encontrada`, retorna `1`, sin `credential_ref` en stderr.

## Do / Don't

- Do: delegar la lectura/escritura en `load_email_accounts`, `remove_email_account`, `save_email_account`, `load_mail_server_config`, `store_mail_server_config` y `remove_mail_server_config`; el borrado del secreto en `delete_stored_credential`.
- Do: mantener la confirmacion literal `CONFIRMAR DESVINCULAR` como primera comprobacion de `_account_remove`, antes de leer disco.
- Do: restaurar el estado previo con `store_mail_server_config`/`save_email_account` ante fallo, re-lanzando el error original.
- Don't: borrar el secreto antes de haber limpiado lo local, ni llamar a `resolve_credential`, ni resolver secretos, ni imprimir `credential_ref` o secretos en stdout/stderr.
- Don't: tocar los correos descargados, los indices, adjuntos o `provision_account.py`/`gui_setup.py`/`autostart.py`.
- Don't: intentar rollback inseguro que escriba secretos o enmascare el error original con un error de rollback.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_account_remove.py` (oracle independiente del contrato) y `tests/frozen_account_unlink_stubs.py` (codigo real offline con dobles inyectados para las tres plataformas).

```frozen-cases
[
  {
    "name": "remove_success_unlinks_and_keeps_messages",
    "argv": ["account", "remove", "<root>", "personal", "CONFIRMAR", "DESVINCULAR"],
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "wincred://gmail-personal", "status": "disconnected"}
    ],
    "servers_store": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 465},
    "messages": {"mail/inbox/nota.md": "correo descargado que debe sobrevivir"},
    "code": 0,
    "stdout": ["{\"account_id\": \"personal\", \"status\": \"unlinked\"}"],
    "stderr": [],
    "secret_deleted": "wincred://gmail-personal",
    "expect_store": []
  },
  {
    "name": "remove_wrong_confirmation_changes_nothing",
    "argv": ["account", "remove", "<root>", "personal", "DESVINCULAR"],
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://KEY", "status": "disconnected"}
    ],
    "code": 1,
    "stdout": [],
    "stderr_has": ["confirmacion"],
    "no_store_write": true
  },
  {
    "name": "remove_missing_confirmation_changes_nothing",
    "argv": ["account", "remove", "<root>", "personal"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"],
    "no_store_write": true
  },
  {
    "name": "remove_unknown_account",
    "argv": ["account", "remove", "<root>", "fantasma", "CONFIRMAR", "DESVINCULAR"],
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://KEY", "status": "disconnected"}
    ],
    "code": 1,
    "stdout": [],
    "stderr_has": ["cuenta no encontrada"]
  },
  {
    "name": "remove_storage_failure_rolls_back",
    "argv": ["account", "remove", "<root>", "personal", "CONFIRMAR", "DESVINCULAR"],
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "keychain://gmail-personal", "status": "disconnected"}
    ],
    "servers_store": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 465},
    "fail": "servers",
    "code": 1,
    "stdout": [],
    "stderr_has": ["no se pudo desvincular la cuenta"],
    "no_store_write": true
  },
  {
    "name": "remove_secret_failure_rolls_back_and_keeps_secret",
    "argv": ["account", "remove", "<root>", "personal", "CONFIRMAR", "DESVINCULAR"],
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "secretservice://gmail-personal", "status": "disconnected"}
    ],
    "servers_store": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 465},
    "fail": "credential",
    "code": 1,
    "stdout": [],
    "stderr_has": ["no se pudo desvincular la cuenta"],
    "secret_not_deleted": "secretservice://gmail-personal",
    "expect_store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "secretservice://gmail-personal", "status": "disconnected"}
    ]
  }
]
```

## Constraints
La desvinculacion es una capa fina sobre `src.email.account_store` (`load_email_accounts(root) -> list`, `remove_email_account(root, account_id) -> dict`, `save_email_account(root, account) -> str`), sobre `src.email.mail_server_store` (`load_mail_server_config(root, account_id) -> dict|None`, `remove_mail_server_config(root, account_id) -> bool`, `store_mail_server_config(root, account_id, config) -> str`) y sobre `src.email.credentials.delete_stored_credential(credential_ref: str) -> None`; la CLI delega el estado en `unlink_email_account` y no reimplementa la transaccion. PARAR y reportar si los modulos o funciones citados no existen con esas firmas, si el orden transaccional no puede poner el borrado del secreto al final, si el rollback necesitara resolver o releer el secreto, si el resultado tuviera que incluir `credential_ref`, si los correos descargados pudieran verse afectados, si la confirmacion literal `CONFIRMAR DESVINCULAR` dejara de exigirse tal cual antes de leer disco, si `credential_ref` o un secreto pudieran aparecer en stdout, stderr o un mensaje de error, o si se necesitara red, subprocess, `eval` o `exec`.