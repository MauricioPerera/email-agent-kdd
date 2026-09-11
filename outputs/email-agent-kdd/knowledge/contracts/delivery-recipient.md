---
task: extract_delivered_to
intent: extraer del mensaje parseado los destinatarios reales de entrega de los headers Delivered-To, X-Original-To y Envelope-To sin canonicalizar variantes
target: src/email/delivery.py
signature: "def extract_delivered_to(message) -> list"
language: python
budget:
  cyclomatic_max: 8
  nesting_max: 3
  lines_max: 50
  params_max: 1
tests: tests/frozen_delivery_recipient.py
deps_allowed: [email]
forbids: [eval, exec, subprocess, network_access, socket, urllib, requests, pickle, filesystem_write, print]
---

## Intent

`extract_delivered_to(message) -> list` recibe un mensaje RFC 5322 ya parseado con la stdlib (`email.message.Message`, como produce `parse_raw_email`) y devuelve la lista de direcciones a las que el servidor REALMENTE entrego el mensaje, leidas de los headers de envelope: `Delivered-To`, `X-Original-To` y `Envelope-To`. Estas direcciones identifican el buzon receptor concreto (incluidos alias, etiquetas `+tag` y variantes con puntos del local part), de modo que la filtracion por destinatario recibido NO depende de los headers `To`/`Cc` ni de que el proveedor trate esas variantes como equivalentes.

**NO se canonicaliza nada**: la direccion se devuelve verbatim tal como el servidor la escribio (sin minusculas, sin quitar puntos del local part, sin quitar `+tag`, sin quitar comentarios). Gmail trata `u.a@gmail.com` y `ua@gmail.com` como el mismo buzon, pero otros proveedores NO; asumir la equivalencia producira resultados equivocados de entrega. Por eso la unica normalizacion permitida es el `strip` del addr-spec extraido.

## Interface

`def extract_delivered_to(message) -> list`

- `message`: objeto `email.message.Message` (o subclase, p. ej. el de `policy.default`) ya parseado; NO se re-parsea bytes ni se toca red ni disco.
- Headers consultados, en este orden de recoleccion: `Delivered-To`, `X-Original-To`, `Envelope-To` (busqueda insensible a mayusculas via `get_all`; se toman TODAS las ocurrencias de cada uno).
- Cada valor de header se interpreta como lista de direcciones con `email.utils.getaddresses` (soporta `a@b`, `<a@b>`, `Nombre <a@b>` y `a@b, c@d`); de cada par `(display_name, addr_spec)` solo se usa `addr_spec` (el `display_name` se descarta). Entradas sin `@` (addr-spec vacio o no direccion) se saltan sin error.
- Devuelve: `list[str]` con los addr-spec verbatim, sin duplicados EXACTOS (dos valores que difieran solo en mayusculas o en puntos NO se consideran iguales) y ordenados lexicograficamente ascendente (representacion estable independiente del orden de los headers).
- Lista vacia `[]` si el mensaje no trae ninguno de los tres headers o ninguno rinde una direccion.
- Lanza: `TypeError` si `message` no es un objeto con `get_all` (no es un mensaje parseado); jamas lanza por contenido del header (un header malformado solo se ignora).

## Invariants

- **Determinista**: la misma entrada produce la misma salida; el orden NO depende del orden en que aparecieron los headers ni de mayusculas del nombre del header.
- **Verbatim, sin canonicalizacion**: jamas se normaliza el addr-spec (ni minusculas, ni puntos del local part, ni `+tag`); la equivalencia entre variantes la decide el usuario al consultar, no la extraccion.
- **Solo headers de envelope**: solo se leen `Delivered-To`, `X-Original-To` y `Envelope-To`; jamas se usan `To`, `Cc`, `Bcc`, `Reply-To` ni `Return-Path` como fuente (no demuestran entrega).
- **Deduplicacion exacta**: solo se elimina el addr-spec identico caracter a caracter.
- **Orden lexicografico ascendente**: salida estable como representacion serializable para el indice (frontmatter `delivered_to:`).
- **Tolerante a headers malformados**: un valor sin direccion valida se ignora sin lanzar; la extraccion jamas falla por contenido del mensaje.
- **Pura y de solo lectura**: no muta `message`, no escribe disco, sin red, sin imprimir, sin ejecutar contenido del header (el header es datos, no codigo).

## Examples

```frozen-inputs
["Delivered-To: user@ardf.dev", "X-Original-To: u.s.e.r+tag@ardf.dev", "Envelope-To: USER@ARDF.dev"]
```

- Mensaje con `Delivered-To: user@ardf.dev` y `X-Original-To: u.s.e.r+tag@ardf.dev` → `["u.s.e.r+tag@ardf.dev", "user@ardf.dev"]` (ambas se conservan verbatim y ordenadas; NO se colapsan por equivalencia de puntos).
- Mensaje con `Delivered-To: USER@ARDF.dev` y `Envelope-To: user@ardf.dev` → `["USER@ARDF.dev", "user@ardf.dev"]` (sin minusculas forzadas; la deduplicacion es exacta).
- Mensaje con `Delivered-To: Mail Delivery System <user@ardf.dev>` → `["user@ardf.dev"]` (el display name se descarta).
- Mensaje con `Envelope-To: a@x.dev, b@x.dev` → `["a@x.dev", "b@x.dev"]` (lista dentro de un solo header).
- Mensaje con solo `To: user@ardf.dev` (sin headers de envelope) → `[]`.
- Mensaje con `Delivered-To: <>` y `X-Original-To: basura-sin-arroba` → `[]` (malformados se saltan).
- Mensaje con `delivered-to: user@ardf.dev` (nombre de header en minusculas) → `["user@ardf.dev"]` (busqueda insensible a mayusculas).

## Do / Don't

- Do: leer los tres headers con `get_all` (todas las ocurrencias) y resolver direcciones con `email.utils.getaddresses` de la stdlib.
- Do: devolver addr-spec verbatim, deduplicado exacto y ordenado lexicograficamente; `[]` cuando no hay nada.
- Do: descartar el display name y saltar valores sin `@` sin error.
- Don't: no uses `To`/`Cc`/`Bcc`/`Return-Path` ni re-parsees bytes del mensaje.
- Don't: no canonicalices nada (minusculas, puntos del local part, `+tag`): la direccion va verbatim.
- Don't: no falles por un header malformado, no imprimas, no escribas disco, no ejecutes el contenido del header.

## Tests

Las propiedades y casos congelados estan en `tests/frozen_delivery_recipient.py`. El oraculo es independiente: NO importa `src.email` ni `delivery.py`; construye los mensajes de prueba con el parser de la stdlib y calcula el esperado con un MODELO DE REFERENCIA reimplementado en el propio test (coleccion de los tres headers via `get_all`, resolucion con `email.utils.getaddresses`, deduplicacion exacta y orden lexicografico). Verifica la estructura del contrato (frontmatter, 7 secciones, firma, regla `PARAR y reportar si`, deps `[email]`, prohibicion de canonicalizacion), el modelo contra el target para cada caso congelado (orden estable, verbatim, dedup exacta, display name descartado, multiples headers, malformados tolerados, lista vacia), y que el resultado de variantes con puntos o mayusculas NO se colapsa.

## Constraints

Presupuestos: ciclomatica <= 8, anidamiento <= 3, lineas <= 50, parametros <= 1. Solo dependencias de `deps_allowed` (`email`; `email.utils`/`email.message` son el mismo paquete). Pura y de solo lectura: sin disco, red, impresion ni ejecucion de contenido. La salida alimenta la clave `delivered_to` del registro de `parse_raw_email` (clave AUSENTE cuando la lista es vacia, para no alterar registros y nodos ya persistidos) y el filtro `para:EMAIL` de `query_email` via el marcador de frontmatter `delivered_to:`. PARAR y reportar si los headers reales de entrega de algun proveedor usan un nombre distinto de los tres pactados (p. ej. `X-Delivered-To`), si se necesitara canonicalizar (minusculas, puntos o `+tag`) para casar con la expectativa del usuario (se documenta la limitacion en vez de canonicalizar), o si un proveedor entrega informacion de envelope no serializable de forma determinista.