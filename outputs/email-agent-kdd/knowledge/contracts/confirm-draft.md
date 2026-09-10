---
task: confirm_email_draft
intent: confirmar un borrador pendiente con la frase exacta del usuario sin enviar nada
target: src/email/confirm.py
signature: "def confirm_email_draft(draft: dict, confirmation: str) -> dict"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_confirm_draft.py
deps_allowed: [hashlib]
forbids: [eval, exec, subprocess, network_access, smtplib]
---

## Intent

Confirmar un borrador en estado `pending` contra la frase de confirmacion exacta del usuario, devolviendo una copia del borrador con estado `confirmed` y un `confirmation_hash` determinista. La funcion solo transforma el objeto en memoria; jamas envia, guarda ni contacta la red.

## Interface

`def confirm_email_draft(draft: dict, confirmation: str) -> dict`

- `draft`: dict de borrador producido por `create_email_draft`, con al menos las claves `id`, `account_id`, `to`, `subject`, `body` y `status`.
- `confirmation`: frase de confirmacion del usuario (str).
- Devuelve: copia superficial nueva del dict `draft` con las mismas claves y valores, salvo `status` que pasa a `"confirmed"` y `confirmation_hash` que se agrega como str.
- Lanza: `ValueError` si `draft` no es `dict`, si le falta alguna de las claves obligatorias, si `draft["status"]` no es exactamente `"pending"`, o si `confirmation` no es `str` exactamente igual a `"CONFIRMAR ENVIO"`.

Frase de confirmacion (regla exacta, sin excepciones): la comparacion es de igualdad exacta contra la cadena `"CONFIRMAR ENVIO"`. Sin `strip`, sin convertir mayusculas/minusculas, sin variantes de acentos ni espacios; cualquier otra cadena (incluidas `"confirmar envio"`, `"CONFIRMAR ENVIO "` o `"  CONFIRMAR ENVIO"`) se rechaza con `ValueError`.

`confirmation_hash` determinista (regla exacta):

`sha256(draft["id"] + "|" + confirmation)` en hexadecimal minusculas. Misma
entrada, mismo hash; sin reloj, sin aleatoriedad, sin `salt` ni secretos.

## Invariants

- La frase de confirmacion se acepta solo por igualdad exacta con `"CONFIRMAR ENVIO"`; ninguna otra entrada es valida jamas.
- Solo se confirma un borrador cuyo `status` es exactamente `"pending"`; un borrador ya `confirmed` o en cualquier otro estado se rechaza con `ValueError`.
- La funcion nunca muta `draft`: el dict de entrada queda intacto y el resultado es una copia nueva.
- La copia conserva todas las claves y valores originales y agrega `status: "confirmed"` y `confirmation_hash`.
- El `confirmation_hash` es `sha256` minuscula de la cadena de la regla determinista; dos llamadas con la misma entrada devuelven el mismo hash.
- La funcion es pura respecto a la red y al disco: no envia, no escribe archivos, no abre sockets y no importa `smtplib`.
- Una entrada invalida se rechaza con `ValueError` antes de construir el resultado y no deja estado parcial.

## Examples

- Ejemplo frozen: borrador `pending` (el del contrato `create-draft`) confirmado con la frase exacta, con `status: "confirmed"` y hash estable.

```frozen-example
{
  "id": "4be77b78ee7b15b413ed7bd5d5745827a7bba0fa4f85a32734846a92c7ed5c28",
  "account_id": "personal",
  "to": ["ana@example.com"],
  "subject": "Hola",
  "body": "Borrador de prueba.",
  "status": "confirmed",
  "confirmation_hash": "0a512837eab16053495647aec4f4b20125fbd92ab4e1d5e0cebd0c34d6742fc1"
}
```

```frozen-inputs
[
  {
    "id": "4be77b78ee7b15b413ed7bd5d5745827a7bba0fa4f85a32734846a92c7ed5c28",
    "account_id": "personal",
    "to": ["ana@example.com"],
    "subject": "Hola",
    "body": "Borrador de prueba.",
    "status": "pending"
  },
  "CONFIRMAR ENVIO"
]
```

Entrada del ejemplo: los dos argumentos del bloque `frozen-inputs`, en orden.

- Casos invalidos que lanzan `ValueError`:

```frozen-invalid-inputs
{"draft": [null, "pending", 7, {}, {"id": "x", "status": "confirmed"}, {"id": "x", "account_id": "a", "to": ["a@x.com"], "subject": "s", "body": "b", "status": "confirmed"}, {"id": "x", "account_id": "a", "to": ["a@x.com"], "subject": "s", "body": "b", "status": "sent"}], "confirmation": ["", "confirmar envio", "CONFIRMAR ENVIO ", "  CONFIRMAR ENVIO", "CONFIRMAR  ENVIO", "CONFIRMAR ENVÍO", "CONFIRMAR ENVIO\n", 7, null]}
```

- `confirm_email_draft(draft, "CONFIRMAR ENVIO")` dos veces con el mismo `draft` devuelve el mismo `confirmation_hash` y dicts iguales pero distintos objetos (`result is not draft`).
- El `draft` de entrada conserva `status: "pending"` tras la llamada: la confirmacion no muta la entrada.

## Do / Don't

- Do: comparar `confirmation` por igualdad exacta contra `"CONFIRMAR ENVIO"`.
- Do: validar que `draft["status"]` sea exactamente `"pending"` antes de confirmar.
- Do: calcular el `confirmation_hash` con `sha256` sobre la cadena exacta documentada y devolver una copia nueva del borrador.
- Don't: enviar el borrador ni usar `smtplib`, sockets o `subprocess`.
- Don't: escribir archivos, tocar la red o depender del reloj o del azar.
- Don't: mutar el dict de entrada, tolerar variantes de la frase o confirmar borradores en otro estado que no sea `pending`.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_confirm_draft.py`. Son oracle independiente: no importan el target ni `src.email`. Verifican el frontmatter del contrato (budgets, deps, forbids), las 7 secciones, la frase exacta de confirmacion, el estado `confirmed` del ejemplo frozen, la no-mutacion del `draft` de entrada y el `confirmation_hash` estable recomputando la regla `sha256` documentada contra el `frozen-example`.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed`. PARAR y reportar si la regla de la frase exacta o del `confirmation_hash` determinista no puede implementarse tal como esta documentada, si la validacion del estado `pending` requiere mas que comparar `draft["status"]`, si un caso invalido no basta con rechazarse con `ValueError`, o si la copia resultante no es serializable a JSON sin perdida.