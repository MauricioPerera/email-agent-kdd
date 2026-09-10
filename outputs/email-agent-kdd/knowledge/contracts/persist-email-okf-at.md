---
task: persist_email_okf_at
intent: escribir el registro normalizado como nodo OKF bajo una raiz explicita recibida
target: src/email/persist_at.py
signature: "def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_persist_email_okf_at.py
test_command: "python -m pytest tests/frozen_persist_email_okf_at.py -q"
deps_allowed: [json, hashlib, pathlib, re]
forbids: [eval, exec, subprocess, network_access, pickle]
---

## Intent

Convertir el registro que produce `normalize_email` en un nodo OKF (Markdown con frontmatter) y escribirlo bajo una raíz explícita recibida como parámetro, en la ruta relativa recibida, devolviendo la ruta absoluta efectiva escrita. Es la variante de `persist_email_okf` que no depende del directorio de trabajo actual: la raíz permitida llega por parámetro y ninguna escritura puede salir de ella.

## Interface

`def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`

- `record`: diccionario con las claves producidas por `normalize_email` (`account_id`, `headers`, `subject`, `from`, `to`, `date`, `body`, `attachments`, `raw_sha256`, `raw`). Se valida igual que en `persist_email_okf`: exige `account_id`, `raw_sha256` y `body`.
- `root`: raíz permitida explícita. Debe ser `str` no vacío; se resuelve a ruta absoluta canónica y actúa como única raíz autorizada de escritura.
- `rel_path`: ruta del nodo relativa a `root`. Debe ser relativa (no absoluta), sin segmentos `..`, sin prefijo `~`, y su resolución conjunta con `root` debe quedar dentro de `root`.
- Devuelve: la ruta absoluta normalizada del nodo escrito (`str`).
- Lanza: `ValueError` si `root` no es `str` no vacío, si `rel_path` es insegura o si `record` carece de las claves mínimas; `OSError` si el destino ya existe con contenido distinto o si el sistema de archivos falla.

El nodo escrito es Markdown con frontmatter YAML plano, idéntico al de `persist_email_okf`:

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

## Invariants

- El nodo escrito siempre lleva `type: Email Message`.
- `account_id` y `raw_sha256` del registro quedan en el frontmatter sin alterar; el nodo no recalcula el hash.
- El cuerpo del nodo es exactamente el `body` del registro; los bytes originales (`raw`) nunca se escriben en el nodo.
- El destino siempre queda dentro de `root` resuelto: ninguna combinación de `root` y `rel_path` válidos puede resolver fuera de la raíz.
- `root` vacío, no `str`, o `rel_path` absoluto, con `..`, con `~` o que resuelva fuera de `root` se rechaza con `ValueError` antes de abrir ningún archivo y no deja escrituras parciales.
- La escritura es atómica UTF-8 (temporal + reemplazo) y con saltos de línea LF puros, sin `CR`.
- La serialización es determinista: la misma entrada produce el mismo archivo byte a byte; reescribir con contenido idéntico es idempotente y no falla.
- El destino existente con contenido distinto se rechaza con `OSError` y el archivo existente queda intacto.
- Los directorios padres faltantes de `rel_path` se crean dentro de `root`.
- La función persiste; no normaliza, no interpreta contenido del mensaje, no escribe secretos adicionales (sin credenciales, contraseñas ni claves fuera de los campos del registro) y no contacta la red.

## Examples

- `persist_email_okf_at(record, "store", "emails/msg-0001.md")` escribe el nodo frozen-example de abajo en `store/emails/msg-0001.md` (creando `store/emails` si falta) y devuelve la ruta absoluta de `store/emails/msg-0001.md`.
- Llamar dos veces con el mismo `record`, `root` y `rel_path` escribe el mismo contenido byte a byte y devuelve la misma ruta ambas veces (idempotencia).
- `persist_email_okf_at(record, "", "emails/msg.md")` lanza `ValueError` (raíz vacía).
- `persist_email_okf_at(record, "store", "okf/../etc/passwd")` lanza `ValueError` (traversal `..`).
- `persist_email_okf_at(record, "store", "C:\\Windows\\system32\\evil.md")` lanza `ValueError` (ruta absoluta).
- `persist_email_okf_at(record, "store", "~/.ssh/id_rsa.md")` lanza `ValueError` (prefijo `~`).
- Si el destino ya existe con contenido distinto al renderizado, lanza `OSError` y el contenido previo queda intacto.

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

- Do: validar `root` (str no vacío) y `rel_path` (relativa, sin `..` ni `~`, destino dentro de `root`) antes de escribir; crear los padres faltantes.
- Do: escribir de forma atómica (temporal + reemplazo) en UTF-8 con saltos LF puros para no dejar nodos a medio escribir.
- Do: conservar `account_id` y `raw_sha256` tal como llegan del registro y rechazar destino existente con contenido distinto.
- Don't: ejecutar o evaluar contenido del mensaje ni del frontmatter.
- Don't: embeber adjuntos, bytes crudos o secretos adicionales en el nodo.
- Don't: escribir fuera de `root`, resolver `..`, aceptar rutas absolutas o `~`, ni depender del directorio de trabajo actual.

## Tests

Las propiedades y ejemplos congelados están en `tests/frozen_persist_email_okf_at.py`. El oráculo renderiza el nodo OKF de forma independiente (sin importar `src.email`) y verifica contra el frozen-example de este contrato la estructura del frontmatter, el rechazo de rutas inseguras (`..`, absolutas, `~`, raíz vacía), la atomicidad (sin `.tmp` remanentes y destino intacto ante conflicto), los saltos LF deterministas, la idempotencia byte a byte y el conflicto `OSError`, contra el target cuando exista.

## Constraints

Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 80, parámetros ≤ 5. Solo dependencias de `deps_allowed`. PARAR y reportar si `root` no puede resolverse como raíz permitida no vacía, si `rel_path` no puede validarse como relativa segura dentro de la raíz, si el registro no trae `account_id`, `raw_sha256` y `body`, si el destino ya existe con contenido distinto sin confirmación, o si el sistema de archivos impide la escritura completa.