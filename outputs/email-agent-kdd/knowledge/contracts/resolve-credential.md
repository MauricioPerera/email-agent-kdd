---
task: resolve_credential
intent: resolver una referencia env:// al secreto de su variable de entorno sin exponerlo
target: src/email/credentials.py
signature: "def resolve_credential(credential_ref: str, environ=None) -> str"
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 40
  params_max: 2
test_command: "python -m pytest tests/frozen_resolve_credential.py"
tests: tests/frozen_resolve_credential.py
deps_allowed: [os, re]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, logging, open, print, getpass, keyring]
---

## Intent

Resolver una referencia de credencial `env://NAME` al secreto guardado en la variable de entorno `NAME`, leyendo del mapping `environ` inyectable (o `os.environ` si es `None`) y devolviendo el secreto UNICAMENTE en memoria como `str`. La funcion jamas imprime, persiste, transforma ni incluye el secreto en mensajes de error; referencias invalidas o variables ausentes/vacias se rechazan con `ValueError`.

## Interface

`def resolve_credential(credential_ref: str, environ=None) -> str`

- `credential_ref`: referencia exactamente con la forma `env://NAME`, donde `NAME` no vacio y compuesto solo por letras ASCII, digitos y `_` (regex `^[A-Za-z0-9_]+$` tras la constante `env://`).
- `environ`: mapping inyectable que provee las variables (se consulta SOLO lectura, con `.get`); si es `None` se usa `os.environ`.
- Devuelve: el valor del mapping para `NAME` (`str`), tal cual, sin transformarlo.
- Lanza: `ValueError` si `credential_ref` no es `str`, no tiene la forma `env://NAME`, tiene un `NAME` vacio o con caracteres fuera de `[A-Za-z0-9_]`; tambien si `NAME` esta ausente en `environ` o su valor es vacio (`""` o solo espacios).

Regla exacta de resolucion:

1. La referencia debe empezar por el prefijo literal `env://`; cualquier otro esquema (`keyring://`, `file://`, etc.) se rechaza con `ValueError` (sin intentar interpretarlo).
2. `NAME` se extrae verbatim del resto de la referencia, sin recortar espacios dentro del nombre ni normalizar a mayusculas/minusculas.
3. El valor se devuelve verbatim: sin `strip`, sin decodificar, sin interpolacion.

## Invariants

- Solo se acepta el esquema `env://`; el resto de referencias se rechaza con `ValueError`.
- El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea ni devuelve en un mensaje de error.
- El secreto se devuelve verbatim, sin transformacion ni normalizacion.
- Los mensajes de `ValueError` describen la causa (referencia invalida, variable ausente, valor vacio) sin contener `NAME` con el valor del secreto, ni el valor leido del mapping.
- `environ=None` usa `os.environ`; `environ` dado se usa tal cual y jamas se muta ni se escribe.
- No hay red, procesos ni disco: no se conecta a proveedores, no abre sockets ni archivos y no importa `smtplib`, `socket`, `urllib`, `requests` ni `subprocess`.

## Examples

Ejemplo frozen: con `environ = {"TEST_EMAIL_AGENT_API_KEY": "sk-fake-123"}`, `resolve_credential("env://TEST_EMAIL_AGENT_API_KEY", environ)` devuelve exactamente `"sk-fake-123"`.

```frozen-inputs
["env://TEST_EMAIL_AGENT_API_KEY", "sk-fake-123"]
```

- Entrada del ejemplo: el par `(credential_ref, valor)` del mapping ficticio offline; la llamada devuelve el valor tal cual.
- `resolve_credential("env://NO_EXISTE_FAKE", {})` lanza `ValueError` y el mensaje no contiene ningun valor de mapping.
- `resolve_credential("keyring://gmail/personal", environ)` lanza `ValueError` (esquema no soportado).
- `resolve_credential("env://", environ)` lanza `ValueError` (nombre vacio).
- `resolve_credential("env://MAL NOMBRE", environ)` lanza `ValueError` (caracteres fuera de `[A-Za-z0-9_]`).

## Do / Don't

- Do: validar `credential_ref` como `str` y contra la forma `env://NAME` con una sola comprobacion de regex antes de leer nada.
- Do: usar `environ` cuando no sea `None` y `os.environ` solo en ese caso; leer con `.get` sin modificar el mapping.
- Do: devolver el valor verbatim y rechazar valores ausentes o vacios con `ValueError` con mensaje generico.
- Don't: imprimir, loguear, persistir o devolver el secreto en excepciones; tampoco incluirlo en `repr`.
- Don't: aceptar otros esquemas (`keyring://`, `file://`, `plain:`), nombres vacios o con caracteres fuera de `[A-Za-z0-9_]`.
- Don't: transformar el valor (`strip`, minusculas, decode) ni mutar `environ`; tampoco abrir archivos, procesos o red.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_resolve_credential.py`. Son oracle independiente y NO importan `src.email` ni `credentials.py`: verifican la estructura del contrato (frontmatter, secciones, firma, regla `PARAR y reportar si`), y ejercitan un modelo de referencia reimplementado en el propio test con las reglas del contrato: aceptacion de `env://NAME` con mapping inyectado, rechazo con `ValueError` de referencias invalidas, nombres mal formados, variables ausentes y valores vacios, devolucion verbatim del valor, y ausencia del secreto en los mensajes de error. Todo offline, con marcadores ficticios (`TEST_EMAIL_AGENT_API_KEY`), sin tocar `os.environ` ni red.

## Constraints

Presupuestos: ciclomatica <= 10, anidamiento <= 3, lineas <= 40, parametros <= 2. Solo dependencias de `deps_allowed` (`os`, `re`; stdlib, sin importar nada de `src.email`). No se toca disco, red ni procesos; el secreto jamas se persiste ni se imprime. PARAR y reportar si la forma de referencia `env://NAME` no cubre el caso real, si el secreto no puede resolverse sin escribirlo a disco o imprimirlo, si los mensajes de error no pueden evitarse sin filtrar el secreto, si `environ` inyectable no basta para pruebas offline, o si se necesitara soportar esquemas distintos de `env://`.