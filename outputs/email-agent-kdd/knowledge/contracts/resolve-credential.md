---
task: resolve_credential
intent: resolver una referencia env:// o wincred:// al secreto (variable de entorno o Windows Credential Manager) sin exponerlo
target: src/email/credentials.py
signature: "def resolve_credential(credential_ref: str, environ=None) -> str"
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 40
  params_max: 2
test_command: "python -m pytest tests/frozen_resolve_credential.py"
tests: tests/frozen_resolve_credential.py
deps_allowed: [os, re, src.email.wincred]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, urllib, requests, pickle, logging, open, print, getpass, keyring]
---

## Intent

Resolver una referencia de credencial al secreto correspondiente, devolviendolo UNICAMENTE en memoria como `str`. Dos esquemas soportados: `env://NAME` lee el secreto del mapping `environ` inyectable (o `os.environ` si es `None`) para la variable `NAME`; `wincred://LABEL` DELEGA EXCLUSIVAMENTE en `src.email.wincred.resolve_windows_credential(ref)` (Windows Credential Manager), SIN pasar `environ`, SIN reimplementar la validacion del backend y SIN fallback. La funcion jamas imprime, persiste, transforma ni incluye el secreto en mensajes de error; referencias invalidas o credenciales ausentes/vacias se rechazan con `ValueError` generico.

## Interface

`def resolve_credential(credential_ref: str, environ=None) -> str`

- `credential_ref`: referencia exactamente con UNA de estas formas:
  - `env://NAME`, donde `NAME` no vacio y compuesto solo por letras ASCII, digitos y `_` (regex `^[A-Za-z0-9_]+$` tras la constante `env://`).
  - `wincred://LABEL`, donde `LABEL` cumple la regex de etiqueta del contrato `store_windows_credential` (`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`); la validacion de la referencia NO se reimplementa aqui, la hace el delegado.
- `environ`: mapping inyectable que provee las variables del esquema `env://` (se consulta SOLO lectura, con `.get`); si es `None` se usa `os.environ`. JAMAS se pasa al backend Windows.
- Devuelve: el secreto tal cual (`str`), verbatim, sin transformarlo.
- Lanza: `ValueError` si `credential_ref` no es `str`, no tiene ninguna de las dos formas validas, o la credencial esta ausente o vacia. Los mensajes son genericos y jamas contienen el secreto.
- Cualquier otro esquema (`keyring://`, `file://`, `plain:`, etc.) se rechaza con `ValueError` (sin intentar interpretarlo).

Regla exacta de resolucion:

1. Si la referencia empieza por el prefijo literal `wincred://`, se DELEGA una unica vez en `src.email.wincred.resolve_windows_credential(credential_ref)` y se devuelve su resultado verbatim. El delegado se importa como nombre a nivel de modulo (`from src.email.wincred import resolve_windows_credential`), de modo que las pruebas offline puedan sustituirlo con `monkeypatch` sobre `src.email.credentials.resolve_windows_credential`.
2. En `wincred://` NO se pasa `environ` al backend Windows, NO se reimplementa la validacion de la etiqueta y NO hay fallback: si el Credential Manager no esta disponible el backend PARA con `RuntimeError` y esa señal se propaga (jamás un fallback inseguro: ni archivo plano, ni variable de entorno, ni texto en claro).
3. En el esquema `env://`, `NAME` se extrae verbatim y el valor se devuelve verbatim: sin `strip`, sin decodificar, sin interpolacion. La variable ausente o vacia (`""` o solo espacios) se rechaza con `ValueError`.

## Invariants

- Solo se aceptan los esquemas `env://` y `wincred://`; cualquier otra referencia se rechaza con `ValueError`.
- El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea ni devuelve en un mensaje de error.
- El secreto se devuelve verbatim, sin transformacion ni normalizacion.
- `wincred://` delega EXCLUSIVAMENTE en `resolve_windows_credential` de `src.email.wincred`: la validacion de la referencia y del backend NO se duplica y `environ` jamas se pasa al backend Windows.
- `wincred://` requiere Windows Credential Manager; NO se acepta fallback inseguro cuando no esta disponible: el `RuntimeError` de PARAR del backend se propaga sin enmascararlo.
- Los mensajes de `ValueError` son genericos: describen la causa (referencia invalida, variable ausente, valor vacio, credencial ausente) sin contener el secreto ni el valor leido.
- `environ=None` usa `os.environ` (solo para `env://`); `environ` dado se usa tal cual y jamas se muta ni se escribe.
- No hay red, procesos ni disco: no se conecta a proveedores, no abre sockets ni archivos y no importa `smtplib`, `socket`, `urllib`, `requests` ni `subprocess`.

## Examples

Ejemplo frozen: con `environ = {"TEST_EMAIL_AGENT_API_KEY": "sk-fake-123"}`, `resolve_credential("env://TEST_EMAIL_AGENT_API_KEY", environ)` devuelve exactamente `"sk-fake-123"`.

```frozen-inputs
["env://TEST_EMAIL_AGENT_API_KEY", "sk-fake-123"]
```

Ejemplo frozen wincred: con un backend falso en memoria que contiene `"gmail-app" -> "app-pass-fake-123"`, `resolve_credential("wincred://gmail-app")` (con el delegado sustituido por el doble que consulta ese backend) devuelve exactamente `"app-pass-fake-123"`.

```frozen-inputs-wincred
["gmail-app", "app-pass-fake-123"]
```

- Entrada del ejemplo env: el par `(credential_ref, valor)` del mapping ficticio offline; la llamada devuelve el valor tal cual.
- Entrada del ejemplo wincred: el par `(label, secret)` del vault falso en memoria; la referencia `wincred://gmail-app` se delega al doble (backend falso con `read(label)`) y devuelve el secreto verbatim.
- `resolve_credential("env://NO_EXISTE_FAKE", {})` lanza `ValueError` y el mensaje no contiene ningun valor de mapping.
- `resolve_credential("wincred://no-existe-fake")` (con el doble) lanza `ValueError` generico: credencial ausente, sin secreto en el mensaje.
- `resolve_credential("keyring://gmail/personal", environ)` y `resolve_credential("file:///tmp/secret", environ)` lanzan `ValueError` (esquema no soportado).
- `resolve_credential("env://", environ)`, `resolve_credential("env://MAL NOMBRE", environ)` lanzan `ValueError`.
- `resolve_credential("wincred://")`, `resolve_credential("wincred://gmail app")`, `resolve_credential("wincred://gmail-app/extra")` y `resolve_credential("WINCRED://gmail-app")` lanzan `ValueError` SIN tocar el backend (la validacion de la referencia precede a la delegacion).

## Do / Don't

- Do: validar `credential_ref` como `str` y elegir el esquema con una sola comprobacion (`startswith("wincred://")` o la regex `env://NAME`) antes de leer nada.
- Do: para `wincred://`, delegar UNA vez en el delegado importado de `src.email.wincred` y devolver su resultado verbatim, sin pasar `environ`.
- Do: para `env://`, usar `environ` cuando no sea `None` y `os.environ` solo en ese caso; leer con `.get` sin modificar el mapping.
- Do: devolver el valor verbatim y rechazar valores ausentes o vacios con `ValueError` con mensaje generico.
- Don't: imprimir, loguear, persistir o devolver el secreto en excepciones; tampoco incluirlo en `repr`.
- Don't: reimplementar la validacion de `wincred://` ni el acceso al Credential Manager; tampoco pasar `environ` al backend Windows.
- Don't: aceptar otros esquemas (`keyring://`, `file://`, `plain:`), nombres/etiquetas malformados o aplicar fallback inseguro cuando el Credential Manager no esta disponible (PARAR y reportar).
- Don't: transformar el valor (`strip`, minusculas, decode) ni mutar `environ`; tampoco abrir archivos, procesos o red.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_resolve_credential.py`. Son oracle independiente y NO importan `src.email` ni `credentials.py`, y JAMAS tocan el Credential Manager real ni `os.environ`: verifican la estructura del contrato (frontmatter, secciones, firma, regla `PARAR y reportar si`, dependencias `os`/`re`/`src.email.wincred`), y ejercitan un modelo de referencia reimplementado en el propio test con las reglas del contrato: para `env://`, aceptacion con mapping inyectado y rechazo con `ValueError` de refs/nombres/valores invalidos; para `wincred://`, un DOBLE explicito —backend falso en memoria con el metodo `read(label) -> str` que lanza `LookupError` si la credencial no existe— y `backend=None` PARA con `RuntimeError` (sin fallback), validando refs malformadas SIN tocar el backend, devolucion verbatim, una unica llamada `read`, y ausencia del secreto en los mensajes de error.

Mecanismo de prueba del doble sin romper la interfaz: como la firma NO admite un parametro de backend, el contrato fija que el delegado sea un nombre a nivel de modulo en `src/email/credentials.py`; una prueba de integracion offline (fuera del oracle, que no importa el target) puede sustituirlo con `monkeypatch.setattr("src.email.credentials.resolve_windows_credential", doble)`, donde `doble` es una funcion que recibe la referencia y consulta un backend falso. El oracle especifica ese protocolo y jamas llama al Credential Manager real ni usa credenciales reales; todo offline, con marcadores ficticios, sin red ni disco.

## Constraints

Presupuestos: ciclomatica <= 10, anidamiento <= 3, lineas <= 40, parametros <= 2. Solo dependencias de `deps_allowed` (`os`, `re`, y la delegacion `src.email.wincred`; sin otras importaciones de `src.email`). No se toca disco, red ni procesos; el secreto jamas se persiste ni se imprime. `wincred://` requiere Windows Credential Manager y delega exclusivamente en `src.email.wincred.resolve_windows_credential` sin pasar `environ` y sin reimplementar validacion; NO se acepta fallback inseguro. PARAR y reportar si la forma de referencia `env://NAME` o `wincred://LABEL` no cubre el caso real, si el secreto no puede resolverse sin escribirlo a disco o imprimirlo, si los mensajes de error no pueden evitarse sin filtrar el secreto, si `environ` inyectable no basta para pruebas offline de `env://` (el doble por `monkeypatch` cubre `wincred://`), si se necesitara un fallback cuando el Credential Manager no este disponible en lugar de PARAR, o si se necesitara soportar esquemas distintos de `env://` y `wincred://`.