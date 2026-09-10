---
task: extract_outgoing_contacts
intent: derivar contactos deduplicados del destinatario To de un mensaje saliente confirmado
target: src/email/outgoing_contacts.py
signature: "def extract_outgoing_contacts(message: dict) -> list"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_extract_outgoing_contacts.py
test_command: "python -m pytest tests/frozen_extract_outgoing_contacts.py -q"
deps_allowed: [email]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, json, os, pathlib, open]
---

## Intent

Derivar los contactos de un mensaje saliente confirmado leyendo únicamente `message["to"]`, para incorporarlos a la libreta (vía `store_email_contacts`) después de un envío exitoso. A diferencia de `extract_contacts` —que lee los headers From/To/Cc de un correo recibido—, aquí solo se considera el destinatario `to` del mensaje saliente: el remitente es la cuenta propia y no debe entrar a la libreta. Es una función pura: sin red, sin disco, sin efectos secundarios y sin exponer secretos ni cuerpo del mensaje.

## Interface

`def extract_outgoing_contacts(message: dict) -> list`

- `message`: `dict` de un mensaje saliente confirmado (el formato de `confirm_email_draft`: `id`, `account_id`, `to`, `subject`, `body`, `status`). Solo se lee la clave `to`; el resto del mensaje se ignora por completo.
- `message` no `dict`, o `message["to"]` ausente, `None` o no `list` => `ValueError` (violación estructural del esquema del mensaje: un mensaje saliente confirmado siempre trae destinatarios). La validación estructural ocurre antes de procesar cualquier elemento y no deja estado parcial.
- Cada elemento de `to` representa UN destinatario y puede ser una dirección simple (`"bob@example.com"`) o con display name en formato RFC (`"Bob Smith <bob@example.com>"`).
- Parseo por elemento: `email.utils.getaddresses([elemento])`; se toma únicamente el PRIMER grupo devuelto (un elemento nunca aporta más de un contacto, aunque el string contenga comas).
- `name`: display name del grupo, verbatim tras `strip()`; `""` si el elemento no trae nombre. `email`: la dirección del grupo tras `strip()` y en minúsculas.
- Entrada inválida por elemento (no es `str`, o el primer grupo no arroja dirección no vacía) => el elemento se IGNORA de forma determinista: no lanza error, no aporta contacto y no altera el orden de los demás (tolerancia de contenido; la severidad estructural se reserva para `to`).
- Deduplicación por `email` en minúsculas conservando la primera aparición: su `name` gana y una repetición nunca lo sobrescribe.
- Devuelve: `list` de `dict`s, cada uno con EXACTAMENTE las claves `{"name": str, "email": str}` — el esquema que `store_email_contacts` valida — en orden de aparición. Lista vacía => `[]`.

## Invariants

- La salida es determinista: la misma entrada produce la misma lista en el mismo orden.
- El email sale siempre en minúsculas y sin espacios de borde; `name` conserva el display name original.
- La deduplicación es por email en minúsculas; la primera aparición gana su `name`.
- Cada contacto devuelto tiene exactamente las claves `name` y `email`, ambas `str`.
- De `message` jamas sale nada salvo los contactos derivados de `to`: ni `subject`, ni `body`, ni `account_id`, ni claves de credenciales (`password`, `secret`, `token`).
- Un elemento inválido se ignora sin lanzar error; `to` ausente o no `list` lanza `ValueError`.
- La función es pura: no escribe, no lee archivos, no toca la red, no importa `smtplib` y no muta `message`.
- La salida es compatible entrada a entrada con el esquema de `store_email_contacts`.

## Examples

- El caso `plain_and_rfc_addresses` de `frozen-cases` mezcla dirección simple y formato RFC: `["ana@example.com", "Bob <BOB@example.com>"]` produce `[{"name": "", "email": "ana@example.com"}, {"name": "Bob", "email": "bob@example.com"}]`.
- El caso `dedup_first_wins` de `frozen-cases` colapsa `"Ana Garcia <ana@example.com>"`, `"ANA@example.com"` y `"Otra <ana@example.com>"` a un único contacto cuyo `name` es `Ana Garcia`.
- El caso `invalid_entries_skipped` de `frozen-cases` contiene cadenas vacías y valores no `str` entremezclados con direcciones válidas: los inválidos se ignoran y los válidos conservan su orden relativo.
- El caso `empty_to` de `frozen-cases` con `to: []` devuelve `[]`.
- El caso `no_secrets` de `frozen-cases` usa el mensaje confirmado completo (con `subject`, `body` y `account_id`); el `expected` solo contiene claves `name` y `email` y ningún valor del cuerpo o asunto aparece en la salida.
- Los casos de `frozen-rejects` lanzan `ValueError`: `to` ausente, `to: "ana@example.com"` (string, no lista), `to: None` y `to: ["ana@example.com", 7]` NO está ahí (el `7` se ignora, no rechaza) — solo la forma estructural rechaza.

## Do / Don't

- Do: parsear cada elemento con `email.utils.getaddresses` y quedarse con su primer grupo.
- Do: normalizar el email a minúsculas antes de deduplicar.
- Do: ignorar silenciosamente los elementos que no arrojan una dirección no vacía.
- Don't: leer `subject`, `body`, `cc`, `bcc` ni ninguna otra clave de `message` distinta de `to`.
- Don't: mutar el `message` de entrada ni persistir nada (eso es `store_email_contacts`).
- Don't: lanzar error por elementos inválidos; la única excepción permitida es `ValueError` por `to` ausente o no `list`.

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_extract_outgoing_contacts.py`. Es un oráculo independiente: no importa `src.email` ni el target; verifica el frontmatter del contrato, sus 7 secciones y la cláusula PARAR, los casos congelados de `frozen-cases` (direcciones simples y RFC, deduplicación primera-gana, entradas inválidas ignoradas, `to` vacío, no-filtración de asunto/cuerpo) y los rechazos estructurales de `frozen-rejects`, además de la coherencia del esquema con `store_email_contacts`.

```frozen-cases
[
  {
    "name": "plain_and_rfc_addresses",
    "message": {
      "id": "d1",
      "account_id": "personal",
      "to": ["ana@example.com", "Bob <BOB@example.com>"],
      "subject": "Hola",
      "body": "Cuerpo secreto de prueba.",
      "status": "confirmed"
    },
    "expected": [
      {"name": "", "email": "ana@example.com"},
      {"name": "Bob", "email": "bob@example.com"}
    ]
  },
  {
    "name": "rfc_name_preserved",
    "message": {
      "id": "d2",
      "account_id": "personal",
      "to": ["Ana Garcia <ANA@example.com>"],
      "subject": "Hola",
      "body": "Cuerpo.",
      "status": "confirmed"
    },
    "expected": [{"name": "Ana Garcia", "email": "ana@example.com"}]
  },
  {
    "name": "dedup_first_wins",
    "message": {
      "id": "d3",
      "account_id": "personal",
      "to": [
        "Ana Garcia <ana@example.com>",
        "ANA@example.com",
        "Otra <ana@example.com>"
      ],
      "subject": "Hola",
      "body": "Cuerpo.",
      "status": "confirmed"
    },
    "expected": [{"name": "Ana Garcia", "email": "ana@example.com"}]
  },
  {
    "name": "invalid_entries_skipped",
    "message": {
      "id": "d4",
      "account_id": "personal",
      "to": ["", "   ", 7, null, {}, "bob@example.com", "Carla <carla@example.com>"],
      "subject": "Hola",
      "body": "Cuerpo.",
      "status": "confirmed"
    },
    "expected": [
      {"name": "", "email": "bob@example.com"},
      {"name": "Carla", "email": "carla@example.com"}
    ]
  },
  {
    "name": "empty_to",
    "message": {
      "id": "d5",
      "account_id": "personal",
      "to": [],
      "subject": "Hola",
      "body": "Cuerpo.",
      "status": "confirmed"
    },
    "expected": []
  },
  {
    "name": "no_secrets",
    "message": {
      "id": "d6",
      "account_id": "personal",
      "to": ["Ana Garcia <ana@example.com>", "bob@example.com"],
      "subject": "Asunto confidencial",
      "body": "Cuerpo confidencial que jamas debe salir.",
      "status": "confirmed",
      "password": "s3cr3t"
    },
    "expected": [
      {"name": "Ana Garcia", "email": "ana@example.com"},
      {"name": "", "email": "bob@example.com"}
    ]
  }
]
```

```frozen-rejects
[
  {"name": "missing_to", "message": {"id": "d7", "account_id": "personal", "subject": "Hola", "body": "x", "status": "confirmed"}},
  {"name": "to_is_string", "message": {"id": "d8", "account_id": "personal", "to": "ana@example.com", "subject": "Hola", "body": "x", "status": "confirmed"}},
  {"name": "to_is_null", "message": {"id": "d9", "account_id": "personal", "to": null, "subject": "Hola", "body": "x", "status": "confirmed"}},
  {"name": "to_is_dict", "message": {"id": "d10", "account_id": "personal", "to": {"ana@example.com": true}, "subject": "Hola", "body": "x", "status": "confirmed"}}
]
```

## Constraints

Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 80, parámetros ≤ 5. Solo dependencias de `deps_allowed` (la stdlib `email`); sin red, disco ni efectos secundarios. PARAR y reportar si `to` no puede interpretarse como lista de destinatarios sin ambigüedad, si distinguir nombre de dirección en un elemento requeriría heurísticas no deterministas, o si la compatibilidad con el esquema de `store_email_contacts` dejara de sostenerse con las claves exactas `{"name", "email"}`.