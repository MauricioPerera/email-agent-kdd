---
task: load_email_contacts
intent: leer la libreta de contactos ya guardada en una raiz explicita sin escribir nada
target: src/email/contact_store.py
signature: "def load_email_contacts(root: str) -> list"
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 40
  params_max: 2
tests: tests/frozen_load_email_contacts.py
test_command: "python -m pytest tests/frozen_load_email_contacts.py -q"
deps_allowed: [json, pathlib]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, logging, getpass, keyring]
---

## Intent

Leer la libreta de contactos que `store_email_contacts` guarda en `<root>/contacts.json` y devolverla como lista, sin escribir nada. Es el paso de solo lectura simétrico al store: la raiz llega por parametro (misma convención que `store_email_contacts`), el archivo ausente se comporta como libreta vacía, las entradas se devuelven tal como están en el archivo y toda la validación/lectura existente del store se reutiliza en lugar de duplicarse.

## Interface

`def load_email_contacts(root: str) -> list`

- `root`: raiz del store explicita. Debe ser `str` no vacío tras `strip`; se resuelve a ruta absoluta canónica igual que en `store_email_contacts`. Lanza `ValueError` si no es `str` no vacío.
- Devuelve: `list` de contactos, cada uno un `dict` con EXACTAMENTE las claves `name` y `email` (el esquema que produce y guarda el store), tal como salen de la lectura/validacion existente del store.
- Orden: la salida conserva el MISMO orden en que están las entradas en el archivo (el store las deja ordenadas por `email` ascendente); `load_email_contacts` NO reordena ni deduplica: solo lee.
- Store ausente (no existe `<root>/contacts.json`): devuelve `[]`.
- Archivo presente pero JSON corrupto, con estructura inesperada (top-level distinto de `{"contacts": [...]}`) o con alguna entrada fuera del esquema exacto: lanza `RuntimeError`.
- Delegación obligatoria: reutiliza la lectura y validación existentes del módulo (`_load_store` y `_validate_contact`); NO duplica las reglas de esquema ni de normalización de email.
- Solo lectura: jamás crea `root`, jamás crea o modifica ningún archivo (tampoco `.tmp`), sin red ni procesos; los mensajes de error jamás incluyen el contenido de las entradas.

## Invariants

- El store se lee siempre de `<root>/contacts.json`; ninguna llamada escribe, crea directorios ni deja archivos residuales.
- Store ausente se comporta como libreta vacía: devuelve `[]` y no crea ni el directorio ni el archivo.
- Roundtrip con el fixture del store: cargar los bytes exactos que escribe `store_email_contacts` devuelve exactamente la lista que store guardó (mismos dicts, mismo orden); re-serializar lo cargado con `json.dumps({"contacts": ...}, sort_keys=True, ensure_ascii=False) + "\n"` reproduce los mismos bytes.
- La salida conserva el orden del archivo: una libreta guardada en un orden dado se devuelve en ese mismo orden (el store la deja ordenada por `email` ascendente; `load` no reordena).
- Cada contacto devuelto es un `dict` con exactamente `name` (`str`) y `email` (`str` no vacío, normalizado por la validación existente); jamas claves extra (`password`, `secret`, `token`) ni `bytes`.
- Archivo corrupto o fuera de esquema => `RuntimeError` sin filtrar contenido en el mensaje y sin alterar el archivo (ni bytes ni presencia).
- Toda validación de `root` ocurre antes de abrir ningún archivo: un rechazo no deja lecturas ni efectos en disco.
- No hay escritura, red ni procesos: no importa `smtplib`, `socket`, `urllib` ni `requests` y no conecta a proveedores.

## Examples

Ejemplo frozen: los bytes de `frozen-inputs` escritos tal cual en `<root>/contacts.json` hacen que `load_email_contacts(root)` devuelva exactamente la lista de `frozen-example` (mismo orden, mismos dicts).

```frozen-example
[{"email": "ana@example.com", "name": "Ana Garcia"}, {"email": "bob@example.com", "name": ""}]
```

```frozen-inputs
{"contacts": [{"email": "ana@example.com", "name": "Ana Garcia"}, {"email": "bob@example.com", "name": ""}]}
```

Cada texto de `frozen-corrupt-stores` escrito tal cual en `<root>/contacts.json` hace que la llamada lance `RuntimeError` y deje el archivo con los mismos bytes.

```frozen-corrupt-stores
[
  "{oops",
  "[]",
  "null",
  "{\"items\": []}",
  "{\"contacts\": {}}",
  "{\"contacts\": [\"ana@example.com\"]}",
  "{\"contacts\": [{\"name\": \"Ana\"}]}",
  "{\"contacts\": [{\"name\": \"Ana\", \"email\": \"ana@example.com\", \"extra\": 1}]}",
  "{\"contacts\": [{\"name\": \"Ana\", \"email\": \"\"}]}"
]
```

- Libreta inexistente (`root` que no existe, o directorio existente sin `contacts.json`) devuelve `[]` y no crea directorio ni archivo ni `.tmp`.
- `load_email_contacts("")` y `load_email_contacts("   ")` lanzan `ValueError` (raiz vacía), igual que `None`, `123` o una `list`.
- Una libreta cuyo orden en el archivo difiere del ascendente por `email` se devuelve en el orden del archivo (no se reordena).

## Do / Don't

- Do: validar `root` (`str` no vacío) antes de tocar el disco y delegar la lectura/corrección de esquema en los helpers existentes del store (`_load_store` / `_validate_contact`).
- Do: devolver la lista en el orden exacto del archivo y `[]` cuando el store no existe.
- Do: propagar `RuntimeError` para store corrupto o fuera de esquema, con mensajes que no contengan contenido de las entradas.
- Don't: escribir, crear directorios, crear o borrar archivos (incluido `contacts.json.tmp`), reordenar, deduplicar ni renormalizar en la carga.
- Don't: duplicar las reglas de esquema o normalización de contacto que ya viven en `contact_store`.
- Don't: depender del directorio de trabajo actual, aceptar `root` vacío o no `str`, ni usar red, reloj ni azar.

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_load_email_contacts.py`. Son oracle independiente: verifican la estructura del contrato (frontmatter, 7 secciones, frase de parada, bloques `frozen-example`, `frozen-inputs` y `frozen-corrupt-stores` bien catalogados y coherentes con las constantes del oracle) y, cuando el target exista, el comportamiento real contra una raiz temporal: roundtrip byte a byte del frozen-example, ausencia devolviendo `[]` sin efectos en disco, orden conservado tal como está en el archivo, cada caso de `frozen-corrupt-stores` lanzando `RuntimeError` sin alterar el archivo, `root` inválida lanzando `ValueError` antes de abrir nada, y ausencia de escrituras/red/secreto.

## Constraints

Presupuestos: ciclomática ≤ 10, anidamiento ≤ 3, líneas ≤ 40, parámetros ≤ 2. Solo dependencias de `deps_allowed` (`json`, `pathlib`; stdlib, sin importar nada de `src.email` como paquete ni `cli.py`). Delega en los helpers existentes de `src/email/contact_store.py` y no duplica sus reglas; no se modifica `src/email/contacts.py`, `src/email/cli.py` ni ningún otro archivo, y no se integra CLI. PARAR y reportar si la lectura/validación existente de `contact_store` no puede reutilizarse sin duplicar reglas, si el esquema guardado difiere de las claves `name` y `email` documentadas aquí, si la distinción entre store ausente y store corrupto no puede lograrse sin escribir en disco, si la ordenación del store ya no fuera el orden por `email` ascendente del contrato de `store_email_contacts`, o si los mensajes de error no pueden escribirse sin filtrar contenido de las entradas.