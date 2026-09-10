---
task: sync-email-account
intent: orquestar la sincronizacion de una cuenta con callables inyectados
target: ../../../../src/email/sync.py
signature: "def sync_email_account(account: dict, fetch_messages, persist_message, update_contacts=None) -> dict"
budget:
  cyclomatic_max: 15
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_sync_email_account.py
test_command: "python -m pytest -q tests/frozen_sync_email_account.py -o python_files=\"frozen_*.py\""
deps_allowed: [typing]
forbids: [eval, exec, subprocess, network_access, filesystem_write, pickle, print]
---
## Intent
Orquestar la sincronizacion de una cuenta ya configurada: obtener los mensajes con `fetch_messages` (inyectado), persistir cada uno una vez en orden con `persist_message` (inyectado) y, si se pasa `update_contacts`, alimentar los contactos con una copia de los mensajes, devolviendo un resumen exacto. La funcion es un orquestador puro: no toca red ni disco por su cuenta.

## Interface
`def sync_email_account(account: dict, fetch_messages, persist_message, update_contacts=None) -> dict`

- `account` (obligatorio): dict con `account_id` (`str` no vacio). La funcion solo lee esta clave; nunca muta `account`.
- `fetch_messages` (obligatorio): callable que recibe `account` y devuelve la lista de mensajes. Se llama EXACTAMENTE una vez, antes de cualquier persistencia.
- `persist_message` (obligatorio): callable que recibe un mensaje (`dict`) y devuelve la ruta del nodo escrito (`str`). Se llama una vez por mensaje, en el orden de la lista, y cada mensaje se persiste UNA sola vez.
- `update_contacts` (opcional): callable que recibe una lista y actualiza los contactos. Si no es `None` se llama EXACTAMENTE una vez, DESPUES de persistir todos los mensajes, con una COPIA de la lista de mensajes (shallow copy: `list(messages)`); mutaciones del receptor no afectan el estado interno. Si es `None` no se llama nunca.
- Devuelve `dict` con EXACTAMENTE las claves `account_id` (`str`), `fetched` (`int`, total de mensajes obtenidos), `persisted` (`int`, total persistidos), `persisted_paths` (`list[str]` en orden de persistencia) y `contacts_updated` (`bool`).
- Errores: toda falla (validacion, `fetch` que no devuelve lista de dicts, o excepcion lanzada por `fetch_messages`, `persist_message` o `update_contacts`) se relanza como `RuntimeError` generico cuyo mensaje incluye el `account_id` y la etapa fallada, sin contenido de mensajes ni secretos.

## Invariants
- Validacion ANTES de cualquier llamada: si `account` no es dict, no trae `account_id`, o este no es `str` no vacio, o `fetch_messages`/`persist_message` no son callables, se lanza `RuntimeError` y `fetch_messages` recibe CERO llamadas.
- `fetch_messages` se invoca exactamente una vez con `account`, y su resultado debe ser `list` de la que cada elemento es `dict`; si no, `RuntimeError` sin persistir nada ni llamar contactos.
- Persistencia estrictamente en orden: `persist_message(msg_1)`, `persist_message(msg_2)`, ..., una vez por mensaje; `persisted_paths` conserva ese orden.
- `update_contacts` solo corre tras COMPLETAR todas las persistencias; recibe una copia (no la lista interna ni los dicts reutilizados por referencia de forma observable); recibe exactamente una llamada.
- `contacts_updated` es `True` solo si `update_contacts` no es `None` y su unica llamada se completo; en otro caso `False`.
- El dict devuelto tiene exactamente 5 claves y ninguna mas: `account_id`, `fetched`, `persisted`, `persisted_paths`, `contacts_updated`.
- `account` y la lista obtenida no se mutan; la funcion no abre sockets, no escribe disco, no loguea secretos y no ejecuta contenido de los mensajes.

## Examples
- `sync_email_account({"account_id": "personal"}, fetch_fake, persist_fake, contacts_fake)` con 3 mensajes y rutas `m1..m3.md` -> `{"account_id": "personal", "fetched": 3, "persisted": 3, "persisted_paths": ["store/emails/m1.md", "store/emails/m2.md", "store/emails/m3.md"], "contacts_updated": True}`; `fetch_fake` llamada 1 vez, persistencias en orden, contacts 1 vez con copia (caso `happy_path_contacts_updated`).
- Bandeja vacia: `fetch` devuelve `[]` -> `fetched: 0`, `persisted: 0`, `persisted_paths: []`, contactos igual llamados 1 vez con lista vacia copiada, `contacts_updated: True` (caso `empty_inbox`).
- `update_contacts=None` -> contacts 0 llamadas, `contacts_updated: False` (caso `contacts_not_configured`).
- `{"email": "yo@x"}` sin `account_id` -> `RuntimeError`, `fetch` 0 llamadas (caso `account_id_missing`).
- `fetch` devuelve un dict (no lista) -> `RuntimeError`, 0 persistencias y 0 llamadas a contactos (caso `fetch_returns_not_list`).
- Un elemento de la lista no es dict -> `RuntimeError` (caso `message_not_dict`).
- `persist_message` falla en el mensaje 2 de 3 -> `RuntimeError` con `account_id`, 0 llamadas a contactos (caso `persist_error_midway`).
- `update_contacts` lanza excepcion -> `RuntimeError`, la sincronizacion ya persistio pero el error se propaga envuelto (caso `contacts_error_wrapped`).

## Do / Don't
- Do: validar `account_id` y los callables antes de la primera llamada externa.
- Do: llamar a `fetch_messages(account)` una unica vez y conservar su lista.
- Do: persistir en orden y acumular las rutas que devuelve `persist_message`.
- Do: pasar `list(messages)` (copia) a `update_contacts`, despues de la ultima persistencia.
- Don't: llamar `fetch_messages` dos veces ni persistir un mensaje dos veces.
- Don't: mutar `account` ni la lista de mensajes, ni escribir disco, ni abrir red, ni loguear contenido de mensajes.
- Don't: exponer secretos o cuerpos de mensajes en mensajes de error; siempre `RuntimeError` generico con `account_id` y etapa.

## Tests
Las propiedades y casos congelados estan en `tests/frozen_sync_email_account.py`. Son oracle independiente: no importan el target ni `src.email`; no abren red ni escriben disco. Verifican la estructura del contrato (frontmatter, presupuestos, 7 secciones, frase de parada) y recomputan cada caso congelado con un modelo de referencia propio (doubles inyectados simulados) contrastando contra los `frozen-cases`: conteo de llamadas (`fetch` 1, persist 1 por mensaje en orden, contacts 1 con copia), claves exactas del resultado, y envoltura de errores en `RuntimeError` generico.

```frozen-cases
[
  {
    "name": "happy_path_contacts_updated",
    "account": {"account_id": "personal"},
    "messages": [{"subject": "uno"}, {"subject": "dos"}, {"subject": "tres"}],
    "fetch_error": null,
    "persist_paths": ["store/emails/m1.md", "store/emails/m2.md", "store/emails/m3.md"],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": null,
      "fetched": 3,
      "persisted": 3,
      "persisted_paths": ["store/emails/m1.md", "store/emails/m2.md", "store/emails/m3.md"],
      "contacts_updated": true,
      "fetch_calls": 1,
      "persist_calls": 3,
      "contacts_calls": 1,
      "contacts_receives_copy": true
    }
  },
  {
    "name": "empty_inbox",
    "account": {"account_id": "work"},
    "messages": [],
    "fetch_error": null,
    "persist_paths": [],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": null,
      "fetched": 0,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": true,
      "fetch_calls": 1,
      "persist_calls": 0,
      "contacts_calls": 1,
      "contacts_receives_copy": true
    }
  },
  {
    "name": "contacts_not_configured",
    "account": {"account_id": "personal"},
    "messages": [{"subject": "solo"}],
    "fetch_error": null,
    "persist_paths": ["store/emails/solo.md"],
    "persist_error_index": null,
    "with_contacts": false,
    "contacts_error": null,
    "expected": {
      "error": null,
      "fetched": 1,
      "persisted": 1,
      "persisted_paths": ["store/emails/solo.md"],
      "contacts_updated": false,
      "fetch_calls": 1,
      "persist_calls": 1,
      "contacts_calls": 0,
      "contacts_receives_copy": false
    }
  },
  {
    "name": "account_id_missing",
    "account": {"email": "yo@example.com"},
    "messages": [],
    "fetch_error": null,
    "persist_paths": [],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": "RuntimeError",
      "fetched": 0,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": false,
      "fetch_calls": 0,
      "persist_calls": 0,
      "contacts_calls": 0,
      "contacts_receives_copy": false
    }
  },
  {
    "name": "fetch_returns_not_list",
    "account": {"account_id": "personal"},
    "messages": {"not": "a list"},
    "fetch_error": null,
    "persist_paths": [],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": "RuntimeError",
      "fetched": 0,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": false,
      "fetch_calls": 1,
      "persist_calls": 0,
      "contacts_calls": 0,
      "contacts_receives_copy": false
    }
  },
  {
    "name": "message_not_dict",
    "account": {"account_id": "work"},
    "messages": ["no-es-dict"],
    "fetch_error": null,
    "persist_paths": [],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": "RuntimeError",
      "fetched": 0,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": false,
      "fetch_calls": 1,
      "persist_calls": 0,
      "contacts_calls": 0,
      "contacts_receives_copy": false
    }
  },
  {
    "name": "persist_error_midway",
    "account": {"account_id": "personal"},
    "messages": [{"subject": "a"}, {"subject": "b"}, {"subject": "c"}],
    "fetch_error": null,
    "persist_paths": ["store/emails/a.md"],
    "persist_error_index": 2,
    "with_contacts": true,
    "contacts_error": null,
    "expected": {
      "error": "RuntimeError",
      "fetched": 3,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": false,
      "fetch_calls": 1,
      "persist_calls": 2,
      "contacts_calls": 0,
      "contacts_receives_copy": false
    }
  },
  {
    "name": "contacts_error_wrapped",
    "account": {"account_id": "work"},
    "messages": [{"subject": "x"}],
    "fetch_error": null,
    "persist_paths": ["store/emails/x.md"],
    "persist_error_index": null,
    "with_contacts": true,
    "contacts_error": "contacts failure",
    "expected": {
      "error": "RuntimeError",
      "fetched": 1,
      "persisted": 0,
      "persisted_paths": [],
      "contacts_updated": false,
      "fetch_calls": 1,
      "persist_calls": 1,
      "contacts_calls": 1,
      "contacts_receives_copy": true
    }
  }
]
```

## Constraints
Presupuestos: ciclomatica <= 15, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed` (`typing`); ninguna externa; la orquestacion usa callables inyectados, nunca implementaciones concretas. PARAR y reportar si la semantica de `fetch_messages`/`persist_message`/`update_contacts` no puede ajustarse a las llamadas documentadas (`fetch(account)`, `persist(message) -> ruta`, `contacts(copia)`), si un error no puede envolverse en `RuntimeError` generico sin exponer secretos o cuerpos, si no se puede garantizar el orden de persistencia o la copia para contactos, si el resultado requiere claves distintas de las 5 documentadas, o si se necesita red, escritura en disco, `subprocess` o mutacion de `account`.