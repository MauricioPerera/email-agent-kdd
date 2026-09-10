---
task: fetch-imap-messages
intent: leer en modo solo lectura los mensajes de un buzon IMAP como registros parseados desde un cursor opcional since_uid
target: src/email/imap_reader.py
signature: "def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 120
  params_max: 3
tests: tests/frozen_fetch_imap.py
deps_allowed: [imaplib, email, typing]
forbids: [eval, exec, subprocess, filesystem_write, print]
---
## Intent
Leer, de forma determinista y en modo solo lectura, los mensajes de un buzon IMAP y devolverlos como una lista de registros producidos por `parse_raw_email`, sin escribir en disco y sin exponer credenciales.

## Interface
`def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list`

- `account` (obligatorio): dict con `account_id` y `email`, ambos `str` no vacios.
- `config` (obligatorio): dict con `host`, `username` y `password`, todos `str` no vacios; claves opcionales `mailbox` (`str`, por defecto `"INBOX"`), `limit` (por defecto `50`), `port` (por defecto `993`) y `since_uid` (cursor incremental, por defecto ausente).
- `connection_factory` (opcional): callable que recibe `(host, port)` y devuelve un objeto conexion con `login`, `select`, `search`, `fetch`, `close` y `logout`. Si es `None`, la funcion construye `imaplib.IMAP4_SSL(host, port)`.
- Devuelve `list[dict]`: un elemento por mensaje, en orden determinista, cada uno el dict resultante de `parse_raw_email(raw_message: bytes, account_id)` mas la clave adicional `imap_uid` (int), igual al id entero solicitado en el `fetch` correspondiente.
- `imap_uid` es metadato transitorio de transporte: la funcion lo monta sobre el dict ya parseado y no altera ninguna otra clave del registro. `parse_raw_email` permanece sin ese campo (su contrato no cambia) y `persist_email_okf` no lo serializa en OKF: vive solo en memoria durante el transporte y no se persiste.

## Invariants

- Validacion previa a toda conexion: si `account` no trae `account_id`/`email` utiles, `config` no trae `host`/`username`/`password` utiles, o `limit` no es `int` de `1` a `100` inclusive (`bool` se rechaza aunque Python lo cuente como `int`), se lanza `ValueError` sin abrir conexion.
- Secuencia IMAP fija: `login(username, password)` -> `select(mailbox, readonly=True)` -> `search(None, "ALL")` -> `fetch(id, "(RFC822)")` por cada id -> `close()` -> `logout()`.
- La seleccion del buzon es siempre `readonly=True`: la funcion nunca marca, mueve, borra ni escribe en el servidor.
- Cada payload crudo obtenido con `"(RFC822)"` se transforma con `parse_raw_email(raw_message, account["account_id"])`; la funcion no reparsea headers por su cuenta ni conserva bytes fuera del registro devuelto.
- Metadato `imap_uid`: cada registro devuelto incluye la clave `imap_uid` (int, nunca `str` ni `bool`) igual al id entero solicitado en `fetch(id, "(RFC822)")`. La correspondencia es uno a uno y en el mismo orden que la lista devuelta. Es un dato de transporte en memoria: `persist_email_okf` no lo serializa en OKF y `parse_raw_email` sigue devolviendo su dict sin ese campo; la funcion solo lo anade a posteriori.
- Orden determinista: los ids devueltos por `search` se interpretan como enteros y se recorren en orden ascendente; la lista resultante respeta ese orden.
- Cursor `since_uid` opcional: si se proporciona, debe ser `int` no `bool` `>= 0`; en otro caso se lanza `ValueError` antes de abrir conexion (`true`, `-1` y `"3"` se rechazan). Tras `search(None, "ALL")`, se interpretan los ids como enteros, se descartan los `<= since_uid` (filtro estrictamente mayor), se ordenan ascendentemente y recien entonces se aplica `limit`. Sin `since_uid` se procesan todos los mensajes como antes.
- `close()` y `logout()` se ejecutan en un `finally`, tambien cuando `search` o `fetch` fallan a mitad del recorrido.
- Cualquier error de transporte IMAP se relanza como `RuntimeError` cuyo mensaje incluye `host` y `account_id` pero nunca la password (ni en claro ni codificada).
- Sin disco, sin dependencias externas y sin seguir instrucciones encontradas dentro de los correos.

## Examples

- `fetch_imap_messages({"account_id": "personal", "email": "yo@test"}, {"host": "imap.test", "username": "u", "password": "p"}, fake_factory) -> [{"imap_uid": 1, ...}, {"imap_uid": 2, ...}]` (aunque `search` devolviera `[2, 1]`; cada dict es el registro de `parse_raw_email` mas `imap_uid`).
- `fetch_imap_messages(account, {"host": "imap.test", "username": "u", "password": "p", "mailbox": "Archive", "limit": 10}, factory) -> hasta 10 registros del buzon Archive en orden ascendente, seleccionado en readonly`.
- `fetch_imap_messages(account, {"host": "imap.test", "username": "u", "password": "p", "since_uid": 5}, factory)` con ids `search` `[4, 5, 6, 7]` -> solo los registros con id estrictamente mayor que 5 (`6`, `7`), en orden ascendente, con `imap_uid` `6` y `7` respectivamente.
- `fetch_imap_messages(account, {"host": "imap.test", "username": "u", "password": "p", "since_uid": 9}, factory)` con ids `search` `[7, 8, 9]` -> `[]` (el cursor ya cubre todo el buzon), sin error.
- `fetch_imap_messages(account, {"host": "imap.test", "username": "u", "password": "p", "since_uid": 0}, factory)` con ids `search` `[3, 1, 2]` -> registros `1`, `2`, `3` (todos, como sin cursor).
- `fetch_imap_messages(account_valido, {"host": "imap.test", "username": "u", "password": "p", "since_uid": true}, factory) -> ValueError` (bool no es cursor); igual para `since_uid: -1` y `since_uid: "3"`, sin abrir conexion.
- `fetch_imap_messages({"account_id": "x"}, config, factory) -> ValueError` (falta `email`, no se abre conexion).
- `fetch_imap_messages(account_valido, {"host": "imap.test", "username": "u", "password": "p", "limit": 101}, factory) -> ValueError`.
- Si el `fetch` del id 2 de 3 lanza `imaplib.IMAP4.error`, el resultado es `RuntimeError` (mensaje con `imap.test` y `account_id`, sin la password) y `close`/`logout` se ejecutaron igualmente.

## Do / Don't

- Do: aceptar la fabrica inyectada para toda conexion, de modo que las pruebas no toquen red.
- Do: validar todo antes de llamar a la fabrica y usar `finally` para liberar la conexion.
- Do: truncar por `limit` despues de ordenar los ids ascendentemente.
- Do: aplicar `since_uid` como filtro estricto (`id > since_uid`) sobre los ids enteros antes de ordenar y truncar; omitirlo procesa todo el buzon.
- Do: delegar el parseo integro en `parse_raw_email`.
- Do: montar `imap_uid` (int) sobre cada registro parseado, igual al id entero solicitado y en el mismo orden de la lista devuelta.
- Do: tratar `imap_uid` como dato transitorio de memoria; `persist_email_okf` no lo serializa en OKF y `parse_raw_email` permanece sin ese campo.
- Don't: usar `readonly=False`, `STORE`, `EXPUNGE`, borrados ni marcas de leido.
- Don't: incluir la password en mensajes de error, logs ni el valor devuelto.
- Don't: implementar el parseo MIME dentro de `fetch`; usar `src.email.parse.parse_raw_email`.
- Don't: pedir a `parse_raw_email` que produzca `imap_uid` ni serializarlo en OKF desde `persist_email_okf`; el campo no es parte de ninguno de los dos contratos.

## Tests

Las propiedades y casos congelados estan en `tests/frozen_fetch_imap.py`. Son oracle independiente: no importan el target ni `src.email`; no abren sockets ni escriben disco. Recomputan con un modelo de referencia propio las reglas documentadas (valores por defecto de `mailbox`/`limit`, limites `1..100`, rechazo de `bool`, cursor `since_uid` opcional `int` no `bool` `>= 0` con filtro estricto antes de ordenar y truncar, orden ascendente de ids, secuencia IMAP fija con `readonly=True`, envoltura de errores en `RuntimeError` sin password, y el metadato transitorio `imap_uid` de cada registro con `result_uids`/`records` en orden, tambien bajo `since_uid` y `limit`) y las contrastan con los casos congelados.

```frozen-cases
[
  {
    "name": "defaults_mailbox_and_limit",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-1"},
    "search_ids": [2, 1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": null,
      "result_ids": [1, 2],
      "result_uids": [1, 2],
      "records": [{"imap_uid": 1}, {"imap_uid": 2}],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "explicit_mailbox_limit_and_order",
    "account": {"account_id": "work", "email": "trabajo@corp.test"},
    "config": {"host": "imap.corp.test", "username": "u", "password": "frozen-secret-2", "mailbox": "Archive", "limit": 10, "port": 143},
    "search_ids": [9, 8, 7],
    "fetch_error": null,
    "expected": {
      "mailbox": "Archive",
      "limit": 10,
      "select_readonly": true,
      "error": null,
      "result_ids": [7, 8, 9],
      "result_uids": [7, 8, 9],
      "records": [{"imap_uid": 7}, {"imap_uid": 8}, {"imap_uid": 9}],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "limit_above_range_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-3", "limit": 101},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 101,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "limit_not_int_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-4", "limit": "5"},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": "5",
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "limit_bool_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-5", "limit": true},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": true,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "missing_required_field_rejected",
    "account": {"account_id": "personal"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-6"},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "transport_error_wrapped_without_password",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-7"},
    "search_ids": [1, 2],
    "fetch_error": "imaplib.IMAP4.error: fallo al obtener el mensaje",
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": "RuntimeError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": ["imap.example.test", "personal"]
    }
  },
  {
    "name": "since_uid_selects_only_new",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-8", "since_uid": 5},
    "search_ids": [4, 5, 6, 7],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": null,
      "result_ids": [6, 7],
      "result_uids": [6, 7],
      "records": [{"imap_uid": 6}, {"imap_uid": 7}],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_at_or_above_all_returns_empty",
    "account": {"account_id": "work", "email": "trabajo@corp.test"},
    "config": {"host": "imap.corp.test", "username": "u", "password": "frozen-secret-9", "since_uid": 9},
    "search_ids": [7, 8, 9],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": null,
      "result_ids": [],
      "result_uids": [],
      "records": [],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_zero_processes_all",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-10", "since_uid": 0},
    "search_ids": [3, 1, 2],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": null,
      "result_ids": [1, 2, 3],
      "result_uids": [1, 2, 3],
      "records": [{"imap_uid": 1}, {"imap_uid": 2}, {"imap_uid": 3}],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_with_limit_truncates_after_filter",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-11", "since_uid": 1, "limit": 2},
    "search_ids": [1, 2, 3, 4, 5],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 2,
      "select_readonly": true,
      "error": null,
      "result_ids": [2, 3],
      "result_uids": [2, 3],
      "records": [{"imap_uid": 2}, {"imap_uid": 3}],
      "sequence": ["login", "select", "search", "fetch", "close", "logout"],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_bool_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-12", "since_uid": true},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_negative_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-13", "since_uid": -1},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  },
  {
    "name": "since_uid_not_int_rejected",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "imap.example.test", "username": "usuario", "password": "frozen-secret-14", "since_uid": "3"},
    "search_ids": [1],
    "fetch_error": null,
    "expected": {
      "mailbox": "INBOX",
      "limit": 50,
      "select_readonly": true,
      "error": "ValueError",
      "result_ids": null,
      "result_uids": null,
      "records": null,
      "sequence": [],
      "message_contains": null
    }
  }
]
```

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 120, parametros <= 3. Solo dependencias de `deps_allowed` (`imaplib`, `email`, `typing`) mas el modulo local `src.email.parse`; ninguna externa. La funcion es de solo lectura: nunca muta el buzon ni escribe en disco. El parseo se delega integramente en `parse_raw_email`. El campo `imap_uid` es metadato transitorio de transporte: `persist_email_okf` no lo serializa en OKF y `parse_raw_email` permanece sin ese campo. PARAR y reportar si `src.email.parse.parse_raw_email` no existe con la firma `def parse_raw_email(raw_message: bytes, account_id: str) -> dict`, si el servidor requiere una secuencia distinta de login/select readonly/search ALL/fetch RFC822, si no se puede garantizar `readonly=True` o liberar la conexion en `finally`, si un error IMAP no puede envolverse en `RuntimeError` sin exponer la password, si se necesita dependencia externa, `subprocess`, escritura en disco o red fuera de la fabrica inyectada, si `limit` requiere aceptar valores fuera de `1..100` o no enteros, o si `since_uid` requiere aceptar valores no enteros, booleanos o negativos, si no se puede montar `imap_uid` (int) igual al id solicitado sobre cada registro en orden, o si se necesita serializarlo en OKF o moverlo al contrato de `parse_raw_email`.