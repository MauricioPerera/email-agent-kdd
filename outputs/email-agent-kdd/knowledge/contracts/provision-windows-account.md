---
task: provision_windows_email_account
intent: aprovisionar de forma segura una cuenta de correo local con el secreto unicamente en el almacenamiento seguro de Windows
target: src/email/provision_account.py
signature: "def provision_windows_email_account(root: str, account_id: str, provider: str, email: str, label: str, secret: str, backend=None) -> dict"
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 50
  params_max: 7
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_provision_windows_account.py -q"
tests: tests/frozen_provision_windows_account.py
deps_allowed: []
forbids: [eval, exec, subprocess, cmdkey, network_access, socket, urllib, requests, smtplib, keyring, getpass, logging, print, open]
---

## Intent

Aprovisionar de extremo a extremo una cuenta de correo local de forma segura: `provision_windows_email_account(root, account_id, provider, email, label, secret, backend=None)` valida las entradas publicas, guarda el secreto UNICAMENTE en el almacenamiento seguro de Windows (Credential Manager) delegando en `store_windows_credential(label, secret, backend)`, construye el registro con `create_email_account` usando la referencia `wincred://<label>` devuelta y persiste la cuenta con `save_email_account(root, account)`. Devuelve SOLO el registro publico (`account_id`, `provider`, `email`, `status`): JAMAS `credential_ref` ni el secreto. El secreto vive solo en memoria durante la llamada. Compatible solo con Windows o con backend inyectado; `backend=None` en no-Windows propaga la PARADA segura de wincred, sin fallback.

## Interface

`def provision_windows_email_account(root: str, account_id: str, provider: str, email: str, label: str, secret: str, backend=None) -> dict`

- `root`: raiz del store de cuentas (`str` no vacio tras `strip`); solo se toca a traves de `save_email_account`.
- `account_id`: identificador local de la cuenta (`str` no vacio tras `strip`); verbatim en el registro.
- `provider`: nombre del proveedor (`str` no vacio tras `strip`); `create_email_account` lo normaliza a `strip().lower()`.
- `email`: direccion de correo cruda (`str` no vacio tras `strip`); `create_email_account` la normaliza a minusculas sin espacios.
- `label`: etiqueta de wincred; su validacion (regex `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`) y su escritura ocurren SOLO dentro de `store_windows_credential`, antes de tocar el backend.
- `secret`: secreto (`str` no vacio); provision lo recibe y lo entrega integro a `store_windows_credential`; jamas lo copia, transforma, persiste, imprime, loguea ni incluye en errores. Solo existe en memoria durante la llamada.
- `backend`: protocolo `write`/`read` de wincred, inyectable para pruebas offline; `backend=None` usa el backend real (Credential Manager via `ctypes`) y en no-Windows (o sin Credential Manager disponible) propaga la `RuntimeError` de PARADA segura, sin fallback.
- Devuelve: `dict` con EXACTAMENTE cuatro claves: `account_id` (verbatim), `provider` (normalizado), `email` (normalizado), `status: "disconnected"`. Sin `credential_ref`, sin el secreto.
- Lanza: `ValueError` generico por entradas publicas invalidas (`root`, `account_id`, `provider`, `email`) ANTES de cualquier efecto; `ValueError` generico de `label`/`secret` invalidos via `store_windows_credential` (tambien antes de tocar el backend); `RuntimeError` propagado si el almacenamiento seguro falla; errores de `save_email_account` propagados tal cual, con mensajes genericos sin el secreto.

Orden exacto (pipeline de delegacion; provision NO reimplementa nada):

1. Validar `root`/`account_id`/`provider`/`email` como `str` no vacio tras `strip`; cualquier entrada invalida lanza `ValueError` sin tocar el backend ni el disco.
2. `ref = store_windows_credential(label, secret, backend)` -> `"wincred://<label>"`. Si falla: NO se construye registro y NO se escribe `accounts.json`.
3. `registro = create_email_account(account_id, provider, email, ref)`.
4. `save_email_account(root, registro)`: `accounts.json` conserva `credential_ref` `wincred://<label>` y NUNCA el secreto.
5. Devolver solo el registro publico `{account_id, provider, email, status}`.

Atomicidad razonable: si `save_email_account` falla, la credencial queda persistida en Credential Manager (residual documentado y aceptable) pero `accounts.json` no cambia; reintentar es seguro porque `store_windows_credential` sobrescribe la misma etiqueta y `save_email_account` reemplaza por `account_id`. Ninguna otra escritura parcial: ni archivos temporales propios, ni estados intermedios en disco.

### Integracion con el formulario local

- El formulario recolecta `secret` SOLO en la memoria de su proceso y llama `provision_windows_email_account` directamente; el valor JAMAS viaja al agente (ni prompts, ni historial, ni logs) y JAMAS se persiste en `accounts.json`.
- En `accounts.json` queda `credential_ref: "wincred://<label>"` (elegido por el llamador, valido para la regex); el formulario recibe el registro publico de 4 claves para confirmar, sin datos de credenciales.
- En no-Windows (o sin Credential Manager disponible) el formulario recibe la PARADA clara (RuntimeError); no se ofrece fallback.

## Invariants

- El retorno tiene EXACTAMENTE las claves `account_id`, `provider`, `email`, `status`: JAMAS `credential_ref`, JAMAS el secreto, ni una cadena que lo contenga.
- El secreto vive solo en memoria durante la llamada: jamas en `accounts.json` (solo la ref `wincred://<label>`), stdout, stderr, excepciones, retorno ni `repr`.
- La escritura del secreto pasa EXCLUSIVAMENTE por `store_windows_credential`; el registro se construye exclusivamente con `create_email_account`; la persistencia exclusivamente con `save_email_account`. Provision no reimplementa ninguna de las tres.
- Validacion de todas las entradas publicas ANTES de la primera escritura: entradas invalidas jamas tocan el backend ni escriben disco.
- Si falla el almacenamiento seguro, NO se escribe cuenta: `accounts.json` sin cambios y sin crear el directorio del store; JAMAS fallback a variable de entorno, archivo plano ni texto en claro.
- Errores genericos: los mensajes describen la causa sin contener el secreto ni detalles del backend.
- `backend=None` propaga la limitacion segura de wincred en no-Windows (`RuntimeError` de PARADA); un backend inyectado se usa tal cual y solo via `write`/`read`.
- Sin red, sin `subprocess`, sin archivos fuera del store de cuentas (y solo via `save_email_account`), sin UI, sin logs; no interpreta la ref ni muta los argumentos de entrada.

## Examples

- Ejemplo frozen: sobre un backend falso en memoria y un `root` temporal del propio oracle, la llamada con los valores del bloque `frozen-inputs` devuelve exactamente el bloque `frozen-example`.

```frozen-inputs
{
  "root": "<temp-oracle>",
  "account_id": "personal",
  "provider": "  Gmail  ",
  "email": "  Ana @ Example.COM ",
  "label": "email-personal",
  "secret": "app-pass-fake-123"
}
```

```frozen-example
{"account_id": "personal", "provider": "gmail", "email": "ana@example.com", "status": "disconnected"}
```

- Entrada del ejemplo: `root` es un directorio temporal propio del oracle; los demas son los valores del bloque `frozen-inputs`, en orden.
- Tras el ejemplo, el backend falso queda con exactamente una llamada `write("email-personal")` y `accounts.json` contiene una sola cuenta con `credential_ref: "wincred://email-personal"` y jamas el secreto.
- `root`, `account_id`, `provider` o `email` vacios, con solo espacios, no `str` (None, 7, b"x") lanzan `ValueError` sin tocar el backend y sin crear `.email-agent`.
- `label` o `secret` invalidos (`""`, `"e mail"`, `"-x"`, `None`, label de 65 caracteres, secret `None`) lanzan `ValueError` generico via `store_windows_credential`, sin llamada al backend y sin crear `.email-agent`.
- Un backend cuyo `write` lanza `RuntimeError` propaga la excepcion y NO deja `accounts.json` ni el directorio del store.
- `backend=None` en no-Windows lanza `RuntimeError` con mensaje claro de PARAR, sin fallback y sin `accounts.json`.
- Reprovisionar el mismo `account_id` reemplaza el registro y sobrescribe la etiqueta: sigue habiendo una sola cuenta y la ref no cambia.

## Do / Don't

- Do: validar las entradas publicas antes de la primera escritura y delegar TODO en `store_windows_credential`, `create_email_account` y `save_email_account`.
- Do: devolver solo el registro publico de 4 claves y dejar `credential_ref` `wincred://<label>` unicamente en `accounts.json`.
- Do: propagar errores genericos sin el secreto y propagar la PARADA de wincred cuando `backend=None` en no-Windows.
- Don't: persistir, imprimir, loguear o devolver el secreto, ni incluirlo en excepciones o `repr`; tampoco aceptar fallback env/plaintext.
- Don't: usar red, `subprocess`, archivos fuera de `save_email_account`, UI ni logs; tampoco interpretar la ref ni reimplementar la creacion o el guardado.
- Don't: escribir la cuenta cuando el almacenamiento seguro fallo, ni mutar los argumentos de entrada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_provision_windows_account.py`. Son oracle independiente: NO importan `src.email` ni el target, y el backend FALSO es OBLIGATORIO (jamás se toca el Credential Manager real); usan directorios temporales propios y secretos ficticios. Verifican la estructura del contrato (frontmatter con budgets y `params_max: 7`, 7 secciones, regla `PARAR y reportar si`, delegacion declarada en `store_windows_credential`/`create_email_account`/`save_email_account`, `accounts.json`, `wincred://`) y ejercitan un modelo de referencia reimplementado en el propio test con las reglas documentadas: exito con registro publico de 4 claves, persistencia en `accounts.json` con la ref y sin el secreto, delegacion conceptual (orden validate-store-create-save y una sola llamada `write`), validaciones previas a todo efecto, secreto no filtrado en retorno/`repr`/disco/errores, fallo del backend sin `accounts.json` ni directorio, y `backend=None` PARANDO sin fallback. Todo offline, sin red y sin servidores.

## Constraints

Presupuestos por funcion: ciclomatica <= 12, anidamiento <= 3, lineas <= 50, parametros <= 7. Solo dependencias de `deps_allowed` (ninguna externa ni de terceros); los unicos imports permitidos son los internos contractuales `src.email.wincred.store_windows_credential`, `src.email.account.create_email_account` y `src.email.account_store.save_email_account` (y stdlib minima si hiciera falta). La funcion jamas imprime, escribe archivos por su cuenta, usa red ni ejecuta procesos; el secreto jamas se persiste, imprime, loguea ni aparece en errores o retorno; jamas se devuelve `credential_ref` al llamador. PARAR y reportar si la delegacion en `store_windows_credential`, `create_email_account` y `save_email_account` no basta para cubrir el caso del formulario, si el secreto no puede vivir solo en memoria durante la llamada, si `accounts.json` necesitara el secreto en claro, si el retorno necesitara incluir `credential_ref` o el secreto, si los mensajes de error no pueden ser genericos sin filtrar el secreto, si se necesitara un fallback inseguro (variable de entorno, archivo plano, keyring) en lugar de PARAR en no-Windows, si se necesitara red, `subprocess`, UI o logs, o si la validacion previa a la primera escritura no pudiera garantizarse.