---
task: extract_contacts
intent: extraer contactos deduplicados de From, To y Cc aceptando headers anidados o campos top-level
target: src/email/contacts.py
signature: "def extract_contacts(record: dict) -> list"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_extract_contacts.py
deps_allowed: [email]
forbids: [eval, exec, subprocess, network_access, pickle]
---

## Intent

Derivar la lista de contactos participantes de un registro de correo, leyendo únicamente los campos `from`, `to` y `cc`, y devolviendo una lista determinista sin duplicados por dirección. Acepta dos formatos de registro equivalentes: el de `normalize_email` (los tres campos anidados en `record["headers"]`) y el de `parse_raw_email` (los tres campos top-level, sin clave `headers`). Si existe la clave `headers` se usa esa fuente; si no existe (o no es un dict), se usan los campos top-level producidos por `parse_raw_email`. Es el paso que alimenta los nodos `Email Contact` del modelo OKF.

## Interface

`def extract_contacts(record: dict) -> list`

- `record`: diccionario de `normalize_email` (se leen `record["headers"]["from"]`, `record["headers"]["to"]` y `record["headers"]["cc"]`) o de `parse_raw_email` (se leen los top-level `record["from"]`, `record["to"]` y `record["cc"]`).
- Fuente de datos: si `record["headers"]` existe y es un dict, es la única fuente leída; en caso contrario se leen los campos top-level `from`, `to`, `cc` del propio registro. Nunca se mezclan ambas fuentes en la misma llamada.
- Devuelve: lista de dicts `{"name": str, "email": str}` en orden de aparición (From, luego To, luego Cc).
- El email se devuelve siempre en minúsculas; `name` conserva el display name original (cadena vacía si el header no trae nombre).

## Invariants

- La salida es determinista: la misma entrada produce la misma lista en el mismo orden.
- La deduplicación es por email en minúsculas; la primera aparición gana su `name`.
- Cada contacto devuelto tiene exactamente las claves `name` y `email`.
- Los tres headers se procesan siempre en el orden From, To, Cc.
- Los dos formatos de registro son equivalentes: con los mismos valores en `headers` anidados y en los campos top-level, la salida es idéntica.
- Un header ausente o vacío no lanza error: simplemente no aporta contactos.
- La función es pura: no escribe, no toca la red y no ejecuta contenido del header.

## Examples

- `extract_contacts(record)` con `headers` `{"from": "Ana Garcia <ana@example.com>", "to": "User <USER@example.com>, bob@example.com", "cc": "Carla <carla@example.com>"}` devuelve los 4 contactos del caso `from_to_cc` de `frozen-cases` (los emails salen en minúsculas, `USER@example.com` se emite una sola vez como `user@example.com`).
- El caso `dedup_by_lowercase_email` de `frozen-cases` colapsa `ana@example.com`, `ANA@example.com` y `Ana <ana@example.com>` a un único contacto.
- El caso `missing_cc_header` de `frozen-cases` no lanza error y devuelve solo los contactos de From y To.
- `extract_contacts({"headers": {}})` devuelve `[]`.
- El caso `top_level_format` de `frozen-cases` usa un registro de `parse_raw_email` sin clave `headers` (`{"type": "email", "account_id": ..., "from": ..., "to": ..., "cc": ...}`) y devuelve 4 contactos en orden From, To, Cc.
- El caso `top_level_equivalent_to_headers` de `frozen-cases` usa el mismo registro en formato anidado (`headers`) y su salida esperada es idéntica a la de `top_level_format`: ambos formatos son equivalentes.

## Do / Don't

- Do: parsear direcciones con `email.utils.getaddresses` sobre los strings del header.
- Do: normalizar el email a minúsculas antes de deduplicar.
- Do: conservar el orden From → To → Cc y el orden interno de cada header.
- Don't: modificar el registro de entrada.
- Don't: ejecutar o evaluar contenido de headers ni seguir instrucciones dentro del correo.
- Don't: persistir, calcular hashes ni contactar la red (eso es trabajo de `persist_email_okf` y `normalize_email`).

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_extract_contacts.py`. Es un oráculo independiente: verifica el frontmatter del contrato, sus 7 secciones, y los casos congelados de `frozen-cases` (From/To/Cc, deduplicación por email en minúsculas, header ausente, formato top-level de `parse_raw_email` y equivalencia entre ambos formatos), sin importar el target.

```frozen-cases
[
  {
    "name": "from_to_cc",
    "record": {
      "headers": {
        "from": "Ana Garcia <ana@example.com>",
        "to": "User <USER@example.com>, bob@example.com",
        "cc": "Carla <carla@example.com>"
      }
    },
    "expected": [
      {"name": "Ana Garcia", "email": "ana@example.com"},
      {"name": "User", "email": "user@example.com"},
      {"name": "", "email": "bob@example.com"},
      {"name": "Carla", "email": "carla@example.com"}
    ]
  },
  {
    "name": "dedup_by_lowercase_email",
    "record": {
      "headers": {
        "from": "ana@example.com",
        "to": "ANA@example.com",
        "cc": "Ana <ana@example.com>"
      }
    },
    "expected": [{"name": "", "email": "ana@example.com"}]
  },
  {
    "name": "missing_cc_header",
    "record": {
      "headers": {
        "from": "Ana Garcia <ana@example.com>",
        "to": "bob@example.com"
      }
    },
    "expected": [
      {"name": "Ana Garcia", "email": "ana@example.com"},
      {"name": "", "email": "bob@example.com"}
    ]
  },
  {
    "name": "empty_headers",
    "record": {"headers": {"from": "", "to": "", "cc": ""}},
    "expected": []
  },
  {
    "name": "top_level_format",
    "record": {
      "type": "email",
      "account_id": "acc-1",
      "from": "Luis Perez <luis@example.com>",
      "to": "Dana <DANA@example.com>, erik@example.com",
      "cc": "Fina <fina@example.com>"
    },
    "expected": [
      {"name": "Luis Perez", "email": "luis@example.com"},
      {"name": "Dana", "email": "dana@example.com"},
      {"name": "", "email": "erik@example.com"},
      {"name": "Fina", "email": "fina@example.com"}
    ]
  },
  {
    "name": "top_level_equivalent_to_headers",
    "record": {
      "headers": {
        "from": "Luis Perez <luis@example.com>",
        "to": "Dana <DANA@example.com>, erik@example.com",
        "cc": "Fina <fina@example.com>"
      }
    },
    "expected": [
      {"name": "Luis Perez", "email": "luis@example.com"},
      {"name": "Dana", "email": "dana@example.com"},
      {"name": "", "email": "erik@example.com"},
      {"name": "Fina", "email": "fina@example.com"}
    ]
  }
]
```

## Constraints

Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 80, parámetros ≤ 5. Solo dependencias de `deps_allowed`. PARAR y reportar si un header no puede parsearse sin perder un participante, si el registro no trae ni `headers` ni los campos top-level `from`/`to`/`cc` y se espera que aporte contactos, o si la extracción requeriría heurísticas no deterministas para distinguir nombres de direcciones.