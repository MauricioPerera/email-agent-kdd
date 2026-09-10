---
task: store_email_account
intent: guardar y leer registros de cuentas de correo en un store JSON local seguro
target: src/email/account_store.py
signature: "def save_email_account(root: str, account: dict) -> str"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_store_email_account.py
deps_allowed: [json, os, pathlib]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, getpass, keyring, logging]
---

## Intent

Persistir localmente los registros que produce `create_email_account` en `<root>/.email-agent/accounts.json` y releerlos, sin conectarse a ningun proveedor y guardando unicamente la referencia opaca `credential_ref` (nunca el secreto). La funcion de escritura crea directorios, reemplaza por `account_id` sin duplicar y escribe de forma atomica; la de lectura devuelve las cuentas ordenadas o `[]` si el store aun no existe.

## Interface

`def save_email_account(root: str, account: dict) -> str`

- `root`: directorio raiz del store (`str` no vacio tras `strip`). Bajo el se crea `<root>/.email-agent/`.
- `account`: registro EXACTO devuelto por `create_email_account`, con las claves `account_id`, `provider`, `email`, `credential_ref`, `status` y ninguna otra.
- Devuelve: la ruta absoluta del archivo `accounts.json` escrito (`str`).
- Lanza: `ValueError` si `root` no es `str` no vacio o si `account` no cumple el esquema del registro.

`def load_email_accounts(root: str) -> list`

- `root`: directorio raiz del store (mismas reglas que `save_email_account`).
- Devuelve: `list` de `dict` con los registros guardados, ordenados por `account_id` ascendente; `[]` si el archivo no existe.
- Lanza: `RuntimeError` si el archivo existe pero esta corrupto o alguna entrada no cumple el esquema.

Esquema exacto del registro (regla de aceptacion, sin excepciones):

1. `account` debe ser `dict` y sus claves deben ser EXACTAMENTE las cinco del registro de `create_email_account`. Cualquier clave extra (por ejemplo `password`, `secret`, `token`) se rechaza.
2. `account_id`, `provider`, `email` y `credential_ref` deben ser `str` no vacios; `status` debe ser exactamente `"disconnected"`.
3. Ningun valor puede ser `bytes` ni otro tipo no serializable a JSON: si un valor no es `str` se rechaza.
4. Los valores se guardan verbatim (sin re-normalizar): la normalizacion ya la hizo `create_email_account`.

Escritura (regla exacta): el archivo es JSON determinista UTF-8, un objeto con la unica clave `accounts` y una lista de registros ordenada por `account_id`, serializado con claves ordenadas y `ensure_ascii=False`, terminado en salto de linea. La escritura es atomica: primero un archivo temporal en el mismo directorio y luego `os.replace`. Si `account_id` ya existe en el store, su entrada se REEMPLAZA (sin duplicados). Los mensajes de error jamas incluyen el contenido de las entradas.

## Invariants

- El store vive siempre en `<root>/.email-agent/accounts.json`; ninguna funcion escribe fuera de esa ruta.
- En disco solo se guardan las cinco claves del registro y `credential_ref` como texto opaco: jamas un secreto, ni claves adicionales, ni `bytes`.
- La escritura es atomica: un fallo entre el temporal y el `replace` no deja un `accounts.json` parcial o truncado.
- El JSON en disco es determinista: mismo contenido, mismos bytes exactos, sin reloj ni azar.
- `load_email_accounts` devuelve los registros ordenados por `account_id` y jamas devuelve claves fuera del esquema (por lo tanto, nunca contrasenias).
- Archivo ausente => `[]`; archivo presente pero corrupto o fuera de esquema => `RuntimeError` sin filtrar contenido sensible en el mensaje.
- Reemplazo por `account_id`: despues de guardar dos veces el mismo `account_id`, el store contiene exactamente una entrada.
- No hay red ni procesos: no se conecta a proveedores, no abre sockets y no importa `smtplib`, `socket`, `urllib` ni `requests`.

## Examples

Ejemplo frozen: guardar el registro de `create_email_account` deja exactamente estos bytes en `<root>/.email-agent/accounts.json`.

```frozen-example
{"accounts": [{"account_id": "personal", "credential_ref": "keyring://gmail/personal", "email": "ana@example.com", "provider": "gmail", "status": "disconnected"}]}
```

```frozen-inputs
[
  "personal",
  "gmail",
  "ana@example.com",
  "keyring://gmail/personal",
  "disconnected"
]
```

Entrada del ejemplo: los cinco valores construyen el registro (mismas reglas de `create-email-account.md`) y se guardan bajo un `root` cualquiera.

- Dos cuentas con `account_id` distintos quedan ordenadas por `account_id` en disco y en `load_email_accounts`, sin importar el orden de guardado.
- Guardar de nuevo `"personal"` con otro `credential_ref` reemplaza la entrada: el store queda con una sola cuenta `"personal"`.

## Do / Don't

- Do: validar `root` (`str` no vacio) y el esquema exacto del registro antes de tocar el disco.
- Do: crear `<root>/.email-agent/` con `mkdir(parents=True, exist_ok=True)` y escribir via archivo temporal + `os.replace`.
- Do: serializar con claves ordenadas, `ensure_ascii=False`, UTF-8 y salto de linea final; ordenar la lista por `account_id`.
- Do: tratar `credential_ref` como referencia opaca: se copia verbatim y jamas se interpreta, abre ni loguea.
- Don't: conectarse a un proveedor, iniciar OAuth, usar `smtplib`, `socket`, `urllib`, `requests` o `subprocess`.
- Don't: aceptar claves extra (`password`, `secret`, `token`), valores `bytes` u otro `status` que no sea `disconnected`.
- Don't: duplicar `account_id`, re-normalizar los valores, depender del reloj o incluir contenido de las entradas en los mensajes de error.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_store_email_account.py`. Son oracle independiente para la estructura del contrato y verifican el comportamiento real contra un store temporal: ejemplo frozen (bytes exactos), round-trip save/load, archivo ausente => `[]`, reemplazo sin duplicados, orden por `account_id`, JSON determinista byte a byte, rechazo con `ValueError` de `root` y registros invalidos, y `RuntimeError` (sin contenido sensible en el mensaje) para archivo corrupto o entradas fuera de esquema.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed` (`json`, `os`, `pathlib`; stdlib, sin importar nada de `src.email`). No se modifica `src/email/account.py` ni `src/email/cli.py`, y no se integra CLI. PARAR y reportar si el esquema de registro de `create_email_account` no coincide con las cinco claves documentadas aqui, si la escritura atomica via temporal + `os.replace` no es viable en la plataforma, si se necesita aceptar claves o secretos adicionales al registro, si `load_email_accounts` tuviera que devolver entradas fuera del esquema, o si los mensajes de error no pueden evitarse sin filtrar contenido de las entradas.