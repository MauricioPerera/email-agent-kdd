---
task: store_windows_credential
intent: guardar y resolver secretos locales en Windows Credential Manager mediante referencias wincred:// sin exponerlos
target: src/email/wincred.py
signature: "def store_windows_credential(label: str, secret: str, backend=None) -> str"
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 40
  params_max: 3
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_store_windows_credential.py -q"
tests: tests/frozen_store_windows_credential.py
deps_allowed: [ctypes, re]
forbids: [eval, exec, subprocess, cmdkey, network_access, socket, urllib, requests, smtplib, logging, open, print, keyring, getpass]
---

## Intent

Guardar un secreto en el almacenamiento seguro local de Windows (Credential Manager) y resolverlo despues, con el secreto pasando UNICAMENTE en memoria: `store_windows_credential(label, secret, backend=None)` persista el secreto bajo una etiqueta segura y devuelve UNICAMENTE la referencia persistible `wincred://<label>` (JAMAS el secreto); `resolve_windows_credential(ref, backend=None)` acepta esa referencia y devuelve el secreto VERBATIM. El backend real (a implementar en el futuro) usa Windows Credential Manager via `ctypes` (advapi32: `CredWrite`/`CredRead`), JAMAS `subprocess` ni `cmdkey`; el backend inyectable permite pruebas offline. Ninguna de las dos funciones imprime, escribe archivos, usa red, persiste el secreto por su cuenta ni lo incluye en mensajes de error; guardar jamas devuelve el secreto.

## Interface

`def store_windows_credential(label: str, secret: str, backend=None) -> str`
`def resolve_windows_credential(ref: str, backend=None) -> str`

Ambas funciones viven en el mismo target; al implementar, anclar `target_line` a la linea de `store_windows_credential` y documentar la linea de `resolve_windows_credential`.

- `label`: etiqueta segura, `str` no vacio que case EXACTAMENTE con `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (1 a 64 caracteres ASCII: el primero letra o digito; el resto letras, digitos, punto, guion o guion bajo). Sin espacios, sin `/`, sin `\`, sin Unicode. Se usa verbatim, sin `strip` ni normalizacion.
- `secret`: secreto, `str` no vacio. Se preserva VERBATIM (sin `strip`, sin decodificar, sin transformacion de ningun tipo).
- `ref`: referencia con la forma EXACTA `wincred://<label>`, donde `<label>` es una etiqueta valida segun la regla anterior. Cualquier otra forma se rechaza con `ValueError`.
- `backend`: objeto inyectable con EXACTAMENTE dos metodos: `write(label, secret) -> None` (persiste o sobrescribe la entrada de esa etiqueta) y `read(label) -> str` (devuelve el secreto de esa etiqueta o lanza `LookupError` si no existe). Cuando `backend=None` se usa el backend REAL (Credential Manager via `ctypes`); en pruebas SIEMPRE se inyecta un backend falso en memoria. Las funciones jamas crean ni mutan el backend mas alla de las llamadas `write`/`read` contractuales.
- `store_windows_credential` devuelve: la referencia `wincred://<label>` construida con la etiqueta verbatim. JAMAS el secreto, ni una cadena que lo contenga.
- `resolve_windows_credential` devuelve: el secreto tal cual lo devolvio `backend.read(label)`, sin transformacion.
- Lanzan `ValueError` con mensaje GENERICO (sin el secreto) si: `label`/`secret` no son `str` validos (store), `ref` no es `str` o esta malformada (resolve), o la credencial no existe o esta vacia en el backend (resolve; `LookupError` del backend se traduce a `ValueError` generico).
- Regla exacta de almacenamiento: `store` valida, llama UNA vez `backend.write(label, secret)` y devuelve `"wincred://" + label`. Es idempotente: guardar dos veces la misma etiqueta devuelve la MISMA referencia y gana el ULTIMO secreto (semantica de sobrescritura del Credential Manager). `resolve` valida la referencia, extrae la etiqueta verbatim, llama UNA vez `backend.read(label)` y devuelve el valor verbatim.

### Integracion con account setup / formulario local

- El formulario local (evolucion no tecnica de `account setup`) recolecta el campo password SOLO en la memoria del proceso del formulario y lo entrega directamente a `store_windows_credential(label, secret)`; el valor JAMAS se envia al agente (ni en prompts, ni en historial, ni en logs) y JAMAS se persiste en `accounts.json`.
- En `accounts.json` SOLO se guarda la referencia `wincred://<label>` en el campo `credential_ref` existente (hoy guarda `env://NOMBRE`); ninguna otra parte del registro cambia.
- El label puede derivarse de datos ya publicos del formulario (por ejemplo `email-<account_id>`, ya validado como etiqueta); la eleccion del label es libre mientras cumpla la regex, y la ref devuelta es la que se guarda.
- La resolucion (`resolve_windows_credential`) ocurre solo en `sync`/`send`, en memoria, y el secreto se descarta al terminar; jamas se escribe a disco ni se imprime.

## Invariants

- Solo se acepta el esquema `wincred://`; cualquier otro esquema (`env://`, `keyring://`, `file://`) o referencia malformada se rechaza con `ValueError`.
- El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea, envia por red ni se incluye en mensajes de error ni en `repr`.
- `store_windows_credential` JAMAS devuelve el secreto: solo la referencia `wincred://<label>`.
- El secreto se guarda y se devuelve verbatim, sin transformacion ni normalizacion.
- Los mensajes de `ValueError` son genericos: describen la causa (etiqueta invalida, secreto invalido, referencia malformada, credencial ausente) sin contener el secreto.
- `backend=None` usa el backend real (Credential Manager via `ctypes`); un backend inyectado se usa tal cual y solo a traves de `write`/`read`.
- El backend real usa `ctypes` contra advapi32; JAMAS `subprocess`, `cmdkey` ni herramientas externas.
- En sistemas NO Windows (o si el Credential Manager no esta disponible), el backend real debe PARAR y reportar una limitacion clara al usuario; JAMAS un fallback inseguro (ni archivo plano, ni variable de entorno, ni texto en claro).
- No hay red, procesos ni escritura de archivos por parte de las funciones: no abren sockets ni archivos y no importan `smtplib`, `socket`, `urllib`, `requests` ni `subprocess`.

## Examples

Ejemplo frozen: con un backend falso en memoria, `store_windows_credential("gmail-app", "app-pass-fake-123", backend)` devuelve exactamente `"wincred://gmail-app"` y `resolve_windows_credential("wincred://gmail-app", backend)` devuelve exactamente `"app-pass-fake-123"`.

```frozen-inputs
["gmail-app", "app-pass-fake-123"]
```

- Entrada del ejemplo: el par `(label, secret)` sobre un backend falso en memoria; guardar devuelve la ref (sin el secreto) y resolver devuelve el secreto verbatim.
- `store_windows_credential("gmail-app", "otro-secreto-falso", backend)` tras el ejemplo devuelve la MISMA ref `"wincred://gmail-app"` y `resolve` devuelve `"otro-secreto-falso"` (idempotencia: gana el ultimo).
- `resolve_windows_credential("wincred://etiqueta.con-puntos_y-guiones", backend)` con esa etiqueta guardada devuelve el secreto con espacios y signos tal cual (verbatim).
- `store_windows_credential("gmail app", "x", backend)`, `store_windows_credential("", "x", backend)`, `store_windows_credential("-gmail", "x", backend)` y labels de 65 caracteres lanzan `ValueError`.
- `store_windows_credential("gmail-app", "", backend)` y `store_windows_credential("gmail-app", None, backend)` lanzan `ValueError`.
- `resolve_windows_credential("env://GMAIL_APP_PASSWORD", backend)`, `resolve_windows_credential("wincred://", backend)`, `resolve_windows_credential("wincred://gmail-app/extra", backend)` y `resolve_windows_credential("wincred://gmail app", backend)` lanzan `ValueError`.
- `resolve_windows_credential("wincred://no-existe-fake", backend)` lanza `ValueError` generico, y el mensaje no contiene ningun secreto.

## Do / Don't

- Do: validar `label` y `secret` como `str` y contra la regex `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (label) antes de tocar el backend; validar `ref` como `wincred://<label>` con una sola comprobacion.
- Do: usar el backend inyectado cuando no sea `None`; delegar en `write`/`read` y no reimplementar el almacenamiento.
- Do: devolver la referencia `wincred://<label>` al guardar y el secreto verbatim al resolver; sobrescribir la misma etiqueta sin error.
- Do: traducir `LookupError` del backend a `ValueError` generico sin detalles del backend.
- Don't: imprimir, loguear, persistir archivos, usar red o `subprocess`/`cmdkey`, ni devolver el secreto al guardar; tampoco incluirlo en excepciones o `repr`.
- Don't: aceptar labels con espacios, separadores de ruta, Unicode, mas de 64 caracteres, o refs con prefijo distinto, vacias o con etiqueta malformada.
- Don't: transformar el secreto (`strip`, minusculas, decode) ni mutar el backend fuera de `write`/`read`; tampoco aplicar fallback inseguro si el almacenamiento seguro no esta disponible.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_store_windows_credential.py`. Son oracle independiente y NO importan `src.email` ni `wincred.py`, y JAMAS tocan el Credential Manager real: verifican la estructura del contrato (frontmatter, 7 secciones, firmas, regla `PARAR y reportar si`, dependencias `ctypes`/`re`, prohibicion de `subprocess`/`cmdkey`, seccion de integracion con `accounts.json`) y ejercitan un modelo de referencia reimplementado en el propio test con las reglas del contrato sobre un backend FALSO en memoria: aceptacion de labels/refs validas, devolucion de la ref (sin el secreto) al guardar, devolucion verbatim al resolver, idempotencia por sobrescritura, rechazo con `ValueError` de labels/secrets/refs invalidos, errores genericos sin el secreto, y PARAR sin fallback cuando no hay backend. Todo offline, con marcadores ficticios, sin red, sin disco y sin `os.environ`.

## Constraints

Presupuestos por funcion: ciclomatica <= 10, anidamiento <= 3, lineas <= 40, parametros <= 3. Solo dependencias de `deps_allowed` (`ctypes`, `re`; stdlib, sin importar nada de `src.email`). Las funciones jamas imprimen, escriben archivos, usan red ni ejecutan procesos; el secreto jamas se persiste por su cuenta, se imprime ni aparece en errores; guardar jamas devuelve el secreto. El backend real (futuro) debe usar `ctypes` contra advapi32 (Windows Credential Manager), JAMAS `subprocess`/`cmdkey`; en sistemas no Windows (o sin Credential Manager disponible) debe PARAR y reportar una limitacion clara al usuario, sin fallback inseguro. PARAR y reportar si la forma `wincred://<label>` con la regex de etiqueta no cubre el caso real del formulario, si el secreto no puede pasarse solo en memoria, si los mensajes de error no pueden ser genericos sin filtrar el secreto, si `store` necesitara devolver el secreto o mas de la referencia, si el backend inyectable no basta para pruebas offline, si se necesitara un fallback inseguro en sistemas no Windows en lugar de PARAR, si se tuviera que persistir el secreto en `accounts.json` o enviarlo al agente desde el formulario, o si se necesitara `subprocess`/`cmdkey`, red, disco o dependencias fuera de `ctypes` y `re`.