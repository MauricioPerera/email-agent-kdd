---
task: persist_email_okf
intent: serializar el registro devuelto por normalize_email a un nodo OKF en la ruta recibida
target: src/email/persist.py
signature: "def persist_email_okf(record: dict, path: str) -> str"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_persist_email_okf.py
deps_allowed: [json, hashlib, pathlib, re]
forbids: [eval, exec, subprocess, network_access, pickle]
---

## Intent

Convertir el registro que devuelve `normalize_email` en un nodo OKF (Markdown con frontmatter) y escribirlo en una ruta recibida, devolviendo la ruta efectiva escrita. Es la puerta de entrada de la evidencia de correo al store de conocimiento.

## Interface

`def persist_email_okf(record: dict, path: str) -> str`

- `record`: diccionario con las claves producidas por `normalize_email` (`account_id`, `headers`, `subject`, `from`, `to`, `date`, `body`, `attachments`, `raw_sha256`, `raw`).
- `path`: ruta destino del nodo OKF. Se resuelve y valida antes de escribir.
- Devuelve: la ruta absoluta normalizada del nodo escrito (`str`).
- Lanza: `ValueError` si `path` es insegura o `record` carece de las claves mínimas; `OSError` propagada si el sistema de archivos falla.

El nodo escrito es Markdown con frontmatter YAML plano:

````markdown
---
type: Email Message
account_id: personal
subject: Hola
from: Ana Garcia <ana@example.com>
to: user@example.com
date: ""
raw_sha256: 33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337
---
Hola desde el MVP.
````

Los adjuntos no se embeben en el nodo: se referencian por `sha256` en una lista `attachments` del frontmatter.

Cuando el registro trae `delivered_to` (lista de direcciones de envelope de entrega de `parse_raw_email`), se agrega la linea `delivered_to: <addr1, addr2>` inmediatamente despues de `to` (cada direccion verbatim, unidas por `", "`; sin canonicalizar variantes de puntos, `+tag` ni minusculas). Si el registro NO trae `delivered_to` (o es lista vacia), la linea NO se emite: los nodos ya persistidos se siguen renderizando byte a byte igual (compatibilidad).

## Invariants

- El nodo escrito siempre lleva `type: Email Message`.
- `account_id` del registro queda en el frontmatter sin alterar.
- `raw_sha256` del registro queda en el frontmatter sin alterar; el nodo no recalcula el hash.
- El cuerpo del nodo es exactamente el `body` del registro; los bytes originales (`raw`) nunca se escriben en el nodo.
- La linea `delivered_to` del frontmatter se emite SOLO si el registro trae la clave con lista no vacia; las direcciones van verbatim (sin minusculas, sin colapsar puntos ni `+tag`), en el orden del registro.
- La serialización es determinista: la misma entrada produce el mismo archivo byte a byte.
- Una ruta insegura se rechaza antes de abrir ningún archivo y no deja escrituras parciales.
- La función persiste; no normaliza, no interpreta contenido del mensaje y no contacta la red.

## Examples

- `persist_email_okf(normalize_email(raw_bytes, "personal"), "store/emails/msg-0001.md")` escribe el nodo frozen-example de abajo y devuelve la ruta absoluta de `store/emails/msg-0001.md`.
- `persist_email_okf(record, "okf/../etc/passwd")` lanza `ValueError` (traversal `..`).
- `persist_email_okf(record, "C:\\Windows\\system32\\evil.md")` lanza `ValueError` (ruta absoluta fuera de raíz permitida).
- `persist_email_okf({}, "store/emails/msg.md")` lanza `ValueError` (registro sin claves mínimas).

```frozen-example
---
type: Email Message
account_id: personal
subject: Hola
from: Ana Garcia <ana@example.com>
to: user@example.com
date: ""
raw_sha256: 33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337
---
Hola desde el MVP.

```

```frozen-unsafe-paths
["okf/../etc/passwd", "C:\\Windows\\system32\\evil.md", "/etc/passwd", "store\\..\\..\\secret.md", "~/.ssh/id_rsa.md"]
```

## Do / Don't

- Do: validar y normalizar la ruta antes de escribir; crear directorios padres faltantes.
- Do: escribir de forma atómica (temporal + reemplazo) para no dejar nodos a medio escribir.
- Do: conservar `account_id` y `raw_sha256` tal como llegan del registro.
- Don't: ejecutar o evaluar contenido del mensaje ni del frontmatter.
- Don't: embeber adjuntos ni los bytes crudos en el nodo.
- Don't: escribir fuera de la raíz permitida o seguir `..` en la ruta.

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_persist_email_okf.py`. Verifican el frontmatter del nodo (`type`, `account_id`, `raw_sha256`, `body`) y el rechazo de rutas inseguras, contra el frozen-example de este contrato, sin importar el target.

## Constraints

Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 80, parámetros ≤ 5. Solo dependencias de `deps_allowed`. PARAR y reportar si la ruta no puede validarse como segura dentro de la raíz permitida, si el registro no trae `account_id`, `raw_sha256` y `body`, si el destino ya existe con contenido distinto sin confirmación, o si el sistema de archivos impide la escritura completa.