---
task: store_email_contacts
intent: persistir una libreta de contactos deduplicada y determinista bajo una raiz explicita recibida
target: src/email/contact_store.py
signature: "def store_email_contacts(root: str, contacts: list[dict]) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_store_email_contacts.py
test_command: "python -m pytest tests/frozen_store_email_contacts.py -q"
deps_allowed: [json, os, pathlib]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, logging, getpass, keyring]
---

## Intent

Persistir la libreta de contactos que produce `extract_contacts` en un único archivo JSON bajo una raíz explícita recibida como parámetro (`<root>/contacts.json`), fusionándola con lo ya guardado y devolviendo el total de contactos únicos en el store tras la actualización. Es el paso que materializa los contactos de los correos sincronizados: la raíz permitida llega por parámetro (variante de `store_email_account` sin dependencia del directorio de trabajo), la deduplicación es por email normalizado, la actualización es idempotente y ninguna escritura puede salir de la raíz.

## Interface

`def store_email_contacts(root: str, contacts: list[dict]) -> int`

- `root`: raíz del store explícita. Debe ser `str` no vacío tras `strip`; se resuelve a ruta absoluta canónica y actúa como única raíz autorizada de escritura. El directorio se crea si falta (`mkdir(parents=True, exist_ok=True)`).
- `contacts`: `list` de contactos, cada uno un `dict` con EXACTAMENTE las claves `name` y `email` (el formato que produce `extract_contacts`). `name` debe ser `str` (puede ser `""`); `email` debe ser `str` no vacío, sin espacios ni caracteres de control, con un solo `@` y partes no vacías a ambos lados.
- Normalización: la clave de deduplicación es `email.strip().lower()`; el email se guarda normalizado en minúsculas y sin espacios de borde; `name` se guarda verbatim.
- Devuelve: `int` con el número total de contactos únicos que quedan en el store tras el merge (no cuántos entraron).
- Lanza: `ValueError` si `root` no es `str` no vacío o si `contacts` o alguna entrada no cumplen el esquema; `RuntimeError` si el store existente está corrupto o alguna entrada guardada no cumple el esquema.

Fusión (regla exacta): si el store existe, sus entradas van primero y luego las nuevas en el orden recibido; la primera aparición de cada email normalizado gana su `name`, tanto en lo existente como en lo nuevo, y una repetición nunca sobrescribe el `name` ya guardado. El archivo resultante es JSON determinista UTF-8: un objeto con la única clave `contacts` y la lista ordenada por `email` ascendente, con claves ordenadas y `ensure_ascii=False`, terminado en salto de línea. La escritura es atómica: primero un archivo temporal en el mismo directorio y luego `os.replace`. Los mensajes de error jamás incluyen el contenido de las entradas.

## Invariants

- El store vive siempre en `<root>/contacts.json`; ninguna llamada escribe fuera de la raíz resuelta.
- La deduplicación es por email normalizado (`strip().lower()`): después de guardar, cada email normalizado aparece exactamente una vez en el store.
- La actualización es idempotente: llamar dos veces con los mismos argumentos deja los mismos bytes exactos y devuelve el mismo número.
- El merge es determinista y preserva el `name` ya guardado: una nueva aparición de un email conocido no cambia su `name`.
- El JSON en disco es determinista: lista ordenada por `email`, claves ordenadas, `ensure_ascii=False`, salto de línea final, sin reloj ni azar; el orden de la entrada no afecta los bytes salvo por el `name` que gana la primera aparición.
- La escritura es atómica: un fallo entre el temporal y el `replace` no deja un `contacts.json` parcial o truncado, y no quedan `.tmp` remanentes.
- Toda validación de `root` y de `contacts` ocurre antes de abrir ningún archivo: un rechazo no deja escrituras parciales ni crea directorios.
- En disco solo se guardan las claves `name` y `email` de cada contacto: jamas un secreto, ni claves extra (`password`, `secret`, `token`), ni `bytes`.
- Store ausente se comporta como libreta vacía; store presente pero corrupto o fuera de esquema => `RuntimeError` sin filtrar contenido en el mensaje y sin alterar el archivo.
- No hay red ni procesos: no se conecta a proveedores y no importa `smtplib`, `socket`, `urllib` ni `requests`.

## Examples

Ejemplo frozen: guardar la lista de `frozen-inputs` en un store vacío deja exactamente estos bytes en `<root>/contacts.json` y devuelve `2` (los tres contactos se deduplican a dos: `ANA@example.com` se normaliza a `ana@example.com`, y su tercera aparición pierde el `name` frente a la primera).

```frozen-example
{"contacts": [{"email": "ana@example.com", "name": "Ana Garcia"}, {"email": "bob@example.com", "name": ""}]}
```

```frozen-inputs
[
  [
    {"name": "Ana Garcia", "email": "ANA@example.com"},
    {"name": "", "email": "bob@example.com"},
    {"name": "Ana Again", "email": "ana@example.com"}
  ]
]
```

- Llamar de nuevo con la misma lista sobre el mismo `root` devuelve `2` otra vez y los mismos bytes (idempotencia).
- Pre-cargar el store con `ana@example.com` bajo el nombre `Old Name` y guardar `{"name": "New Name", "email": "ana@example.com"}` más `bob@example.com` devuelve `2` y conserva `Old Name` (el merge no sobrescribe el nombre guardado).
- `store_email_contacts("", [])` y `store_email_contacts("   ", [])` lanzan `ValueError` (raíz vacía).
- Guardar `contacts` que no sea `list`, entradas que no sean `dict`, con claves extra o faltantes, con `email` vacío, con espacios en el email o con `name` no `str` lanza `ValueError` antes de escribir y no deja archivos en la raíz.

```frozen-invalid-contacts
[
  "not-a-list",
  [{"name": "Ana", "email": "ana@example.com", "extra": 1}],
  [{"name": "Ana"}],
  [{"name": "Ana", "email": ""}],
  [{"name": "Ana", "email": "ana example.com"}],
  [["ana@example.com"]]
]
```

## Do / Don't

- Do: validar `root` (`str` no vacío) y el esquema exacto de cada contacto antes de tocar el disco.
- Do: normalizar el email con `strip().lower()` como clave de deduplicación y guardarlo normalizado.
- Do: fusionar con lo existente (existentes primero, primera aparición gana el `name`) y ordenar la lista por `email`.
- Do: crear `root` con `mkdir(parents=True, exist_ok=True)` y escribir via archivo temporal + `os.replace`, con claves ordenadas, `ensure_ascii=False`, UTF-8 y salto de línea final.
- Don't: escribir fuera de `root` resuelto, aceptar rutas absolutas en el nombre del store ni depender del directorio de trabajo actual.
- Don't: aceptar claves extra (`password`, `secret`, `token`), valores `bytes`, emails vacíos, con espacios o sin `@`, o `name` no `str`.
- Don't: sobrescribir el `name` ya guardado en el merge, duplicar emails, depender del reloj ni incluir contenido de las entradas en los mensajes de error.

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_store_email_contacts.py`. Son oracle independiente para la estructura del contrato (frontmatter, 7 secciones, frase de parada, frozen-example y frozen-invalid-contacts bien catalogados, render independiente byte a byte) y verifican el comportamiento real contra un store temporal cuando el target exista: éxito y bytes exactos del frozen-example, deduplicación por email normalizado con primera aparición ganando el `name`, idempotencia byte a byte y de retorno, merge con `name` ya guardado, raíz explícita (ruta dentro de `root`, directorio creado), rechazo con `ValueError` de raíz inválida y de los casos de `frozen-invalid-contacts` sin escrituras parciales.

## Constraints

Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 80, parámetros ≤ 5. Solo dependencias de `deps_allowed` (`json`, `os`, `pathlib`; stdlib, sin importar nada de `src.email`). No se modifica `src/email/contacts.py`, `src/email/persist_at.py` ni `src/email/cli.py`, y no se integra CLI. PARAR y reportar si el formato de contacto de `extract_contacts` no coincide con las claves `name` y `email` documentadas aquí, si la escritura atómica via temporal + `os.replace` no es viable en la plataforma, si se necesitara conservar más campos por contacto (por ejemplo `last_seen` o conteos) que rompan el esquema mínimo, si el store existente no puede leerse sin ambigüedad de esquema, o si los mensajes de error no pueden escribirse sin filtrar contenido de las entradas.