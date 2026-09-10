---
task: create_email_draft
intent: construir un borrador de correo serializable sin enviar nada
target: src/email/draft.py
signature: "def create_email_draft(account_id: str, to: list, subject: str, body: str) -> dict"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_create_draft.py
deps_allowed: [email, hashlib]
forbids: [eval, exec, subprocess, network_access, smtplib]
---

## Intent

Convertir los datos crudos de un borrador (cuenta, destinatarios, asunto y cuerpo) en un diccionario de borrador serializable con `id` determinista, estado `pending` y destinatarios normalizados. La función solo construye el objeto; jamas envia, guarda ni contacta la red.

## Interface

`def create_email_draft(account_id: str, to: list, subject: str, body: str) -> dict`

- `account_id`: identificador de la cuenta emisora (str no vacio tras `strip`).
- `to`: lista de direcciones crudas (str); pueden traer espacios, mayusculas o duplicados.
- `subject`: asunto del borrador (str no vacio tras `strip`).
- `body`: cuerpo del borrador (str no vacio).
- Devuelve: `dict` serializable a JSON con las claves `id`, `account_id`, `to`, `subject`, `body`, `status`, en ese orden.
- Lanza: `ValueError` si `account_id` no es `str` no vacio, si `to` no es lista o contiene entradas que no son `str`, si tras normalizar `to` queda vacia, o si `subject`/`body` no son `str` no vacios.

Normalizacion de destinatarios (regla exacta, sin excepciones):

1. Cada entrada se recorta (`strip`).
2. Se descartan las entradas que quedan vacias.
3. El resultado se pasa a minusculas (la direccion completa, no solo el dominio).
4. Se deduplica conservando el orden de primera aparicion.

`id` determinista (regla exacta):

`sha256(account_id + "|" + ",".join(to_norm) + "|" + subject + "|" + body)` en
hexadecimal minusculas. Misma entrada, mismo `id`; sin reloj, sin aleatoriedad.

## Invariants

- El borrador devuelto siempre lleva `status: "pending"`; la funcion no lo cambia jamas.
- El `id` es `sha256` minuscula de la cadena de la regla determinista; dos llamadas con la misma entrada devuelven el mismo `id`.
- `to` en el borrador es exactamente la lista normalizada por la regla de la Interface, sin duplicados ni vacios.
- `account_id`, `subject` y `body` se copian al borrador sin alterar (sin `strip`).
- Todas las claves del borrador son `str` y los valores solo `str` o `list` de `str`: el dict es serializable a JSON.
- La funcion es pura respecto a la red y al disco: no envia, no escribe archivos, no abre sockets y no importa `smtplib`.
- Una entrada invalida se rechaza con `ValueError` antes de construir el borrador y no deja estado parcial.

## Examples

- Ejemplo frozen: destinatarios crudos con espacios, mayusculas, duplicado y vacio se reducen a una direccion, con `id` estable.

```frozen-example
{
  "id": "4be77b78ee7b15b413ed7bd5d5745827a7bba0fa4f85a32734846a92c7ed5c28",
  "account_id": "personal",
  "to": ["ana@example.com"],
  "subject": "Hola",
  "body": "Borrador de prueba.",
  "status": "pending"
}
```

```frozen-inputs
["personal", [" Ana@Example.com ", "ana@example.com", ""], "Hola", "Borrador de prueba."]
```

Entrada del ejemplo: los cuatro argumentos del bloque `frozen-inputs`, en orden.

- Casos invalidos que lanzan `ValueError`:

```frozen-invalid-inputs
{"account_id": ["", "   ", 7, None], "to": [[], ["a@x.com", 3], "a@x.com", ["", "   "]], "subject": ["", "   ", 9, None], "body": ["", None]}
```

- `create_email_draft("personal", ["B@X.com", "b@x.com"], "Hola", "cuerpo")` produce `to == ["b@x.com"]` (dedup conservando orden) y el mismo `id` que llamarlo con `["b@X.com", "B@x.com"]` (la normalizacion hace equivalente el orden de entradas que colapsan al mismo destino).

## Do / Don't

- Do: normalizar destinatarios con la regla de la Interface y deduplicar conservando orden.
- Do: calcular el `id` con `sha256` sobre la cadena exacta documentada.
- Do: rechazar entradas invalidas con `ValueError` antes de construir el dict.
- Don't: enviar el borrador ni usar `smtplib`, sockets o `subprocess`.
- Don't: escribir archivos, tocar la red o depender del reloj o del azar.
- Don't: alterar `account_id`, `subject` o `body`, ni aceptar claves extra en el borrador.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_create_draft.py`. Son oracle independiente: no importan el target ni `src.email`. Verifican el frontmatter del contrato (budgets, deps, forbids), las 7 secciones, la semantica de normalizacion y el `id` determinista recomputando la regla `sha256` documentada contra el `frozen-example`, el estado `pending` y los campos obligatorios del borrador.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed`. PARAR y reportar si la regla de normalizacion o del `id` determinista no puede implementarse tal como esta documentada, si un destinatario no puede validarse como direccion utilizable, si `to`, `account_id`, `subject` o `body` son invalidos y el rechazo con `ValueError` no basta, o si el borrador resultante no es serializable a JSON sin perdida.