---
task: cli_account_setup
intent: agregar el subcomando account setup ROOT como flujo guiado interactivo de alta de cuenta para usuarios no tecnicos
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_account_setup.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_account_setup.py -q
deps_allowed: [argparse, sys, json, pathlib]
forbids: [eval, exec, subprocess, network_access, getpass]
---
## Intent
Exponer en la CLI local de correo el subcomando `account setup ROOT`: un asistente interactivo pregunta por pregunta, pensado para un usuario no tecnico, que da de alta una cuenta pidiendo por `input()` UNICAMENTE el identificador, el proveedor, el correo electronico y el NOMBRE de la variable de entorno que guarda la credencial (jamás se pide, se lee ni se imprime la contraseña ni su valor); construye la referencia como `env://NOMBRE`, delega la creacion y el guardado en el modulo de cuentas ya existente e imprime una sola confirmacion publica. La credencial es una clave de aplicacion que se resuelve mas tarde (en `sync`/`send`); el setup NO se conecta a ningun proveedor ni valida la credencial.

## Interface
`def cli_main(argv: list) -> int` (misma funcion ya implementada; se agrega la rama `account setup`, no se reemplaza nada).

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe contener `usage:`, `account setup ROOT` y los subcomandos ya existentes `search`, `account add`, `account list`, `query`, `sync`, `draft` y `send`) y retorna `0`.
- `account setup ROOT` (exactamente un argumento tras el subcomando): imprime en stdout UNA linea introductoria que contiene la palabra `cancelar` (indica como abortar), y luego hace CUATRO preguntas en este orden, cada una escrita con `input()` y su respuesta recortada con `strip()`:
  1. identificador de la cuenta (ACCOUNT_ID),
  2. proveedor (PROVIDER, solo `gmail` u `outlook`),
  3. correo electronico (EMAIL),
  4. nombre de la variable de entorno de la credencial (por ejemplo `GMAIL_APP_PASSWORD`), dejando claro que se pide el NOMBRE de la variable y no la clave.
  Al reunir las cuatro respuestas construye el registro delegando en `src.email.account.create_email_account(account_id, provider, email, credential_ref)` con `credential_ref = "env://" + NOMBRE` (NOMBRE verbatim tras strip), lo persiste con `src.email.account_store.save_email_account(root, account)` e imprime en stdout EXACTAMENTE una linea `account saved: ACCOUNT_ID` (verbatim) y retorna `0`. La secuencia completa en stdout de un setup exitoso es: intro, las cuatro preguntas, la confirmacion; nada mas.
- Cancelacion: si la respuesta de cualquier pregunta (tras strip, en minusculas) es `cancelar` o `cancel`: mensaje amigable generico en stderr que contiene `cancelado`, nada mas en stdout, NINGUNA escritura en el store, retorna `1`.
- Entrada terminada (EOFError o KeyboardInterrupt al llamar `input()`): mismo tratamiento que la cancelacion (mensaje generico en stderr con `cancelado`, nada escrito, retorna `1`), sin traceback.
- Respuesta vacia o en blanco (tras strip) en cualquier pregunta: mensaje generico amigable en stderr, nada mas impreso, NINGUNA escritura, retorna `1`.
- Proveedor no admitido (distinto de `gmail`/`outlook` tras strip y minusculas): mensaje generico amigable en stderr que indica que solo se admiten `gmail` u `outlook`, NINGUNA escritura, retorna `1`.
- Nombre de variable de entorno invalido (que no case con `[A-Za-z_][A-Za-z0-9_]*`): mensaje generico amigable en stderr, NINGUNA escritura, retorna `1`.
- Errores de datos/almacenamiento (cualquier `ValueError` de `create_email_account` o `ValueError`/`RuntimeError` de `save_email_account`): mensaje generico amigable en stderr (sin `credential_ref`, sin detalles de la excepcion), retorna `1`; lo ya preguntado puede quedar en stdout pero no se imprime ninguna confirmacion.
- Errores de argumentos (argv vacio, `account` con subcomando no reconocido, o `account setup` con un numero de argumentos distinto de uno): mensaje amigable seguido del usage en stderr, retorna `2`.
- Conservacion: `search ROOT QUERY`, `account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF`, `account list ROOT`, `query ROOT INSTRUCTION`, `sync ROOT ACCOUNT_ID [HOST]`, `draft ROOT ACCOUNT_ID TO SUBJECT BODY` y `send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR_ENVIO` conservan exactamente su semantica ya congelada (mismos parseos, mismos codigos `0`/`1`/`2`, mismas salidas); la unica adicion es `account setup` y su linea en el usage.

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- Delegacion pura: la unica fuente del registro es `src.email.account.create_email_account` y la unica via de persistencia es `src.email.account_store.save_email_account`; la CLI no revalida, no renormaliza ni reconstruye el registro por su cuenta.
- `credential_ref` se forma UNICAMENTE como `"env://" + NOMBRE` a partir de la respuesta del usuario; la CLI nunca resuelve la credencial, nunca lee el valor de la variable de entorno y nunca la escribe a disco.
- Jamas se pide la contrasena por `input()`, ni con `getpass` ni de ninguna otra forma; jamas se imprime la contrasena, el valor de la variable de entorno ni el `credential_ref` en stdout ni en stderr; los mensajes de error son genericos (sin detalles de la excepcion, sin tracebacks).
- El setup exitoso imprime en stdout unicamente el dialogo guiado (intro + cuatro preguntas) y UNA confirmacion publica `account saved: ACCOUNT_ID`; ninguna otra linea de estado o de resultado.
- El setup nunca afirma ni menciona mecanismos de autenticacion del proveedor: ni la ayuda ni los prompts ni los errores nombran OAuth ni prometen autenticacion; solo registra la referencia a la clave de aplicacion.
- El codigo `0` solo corresponde a `--help`/`-h` y a los subcomandos ya congelados exitosos; en `account setup`, `0` solo tras un guardado exitoso con su confirmacion impresa.
- El codigo `2` solo corresponde a errores de argumentos/subcomando (con usage en stderr); el codigo `1` a cancelacion, entrada terminada, respuesta invalida, datos invalidos o error de almacenamiento.
- Cancelacion, EOF, respuesta vacia, proveedor no admitido y nombre de variable invalido NO escriben nada en el store: si el store no existia, no se crea.
- Las preguntas van a stdout (dialogo guiado); usage y mensajes de error van a stderr, siempre genericos.
- La funcion es determinista, no toca la red, no ejecuta procesos ni contenido leido; la unica escritura en disco es la que hace `save_email_account` dentro del root indicado.
- Los subcomandos ya existentes (`search`, `account add/list`, `query`, `sync`, `draft`, `send`) quedan intactos: mismos comportamientos, mismos codigos y mismos mensajes; la unica adicion es `account setup` y su linea en el usage.

## Examples

- `cli_main(["--help"])` -> imprime usage con `account setup ROOT` y los subcomandos ya existentes, retorna `0`.
- `cli_main(["account", "setup", "<root>"])` con respuestas `personal`, `Gmail`, `Yo@Example.com`, `GMAIL_APP_PASSWORD` -> imprime intro, las cuatro preguntas y `account saved: personal`, retorna `0`; queda `<root>/.email-agent/accounts.json` con `account_id=personal`, `provider=gmail`, `email=yo@example.com`, `credential_ref=env://GMAIL_APP_PASSWORD`, `status=disconnected`.
- Mismo flujo con `outlook` y `OUTLOOK_APP_PASSWORD` -> `account saved: trabajo` y registro con `provider=outlook`.
- Setup con `account_id` ya existente -> guarda y reemplaza el registro por account_id (semantica de `save_email_account`), imprime `account saved: ACCOUNT_ID` y retorna `0`.
- Respuesta de proveedor `protonmail` -> mensaje generico en stderr (solo gmail u outlook), nada escrito, retorna `1`.
- Respuesta de variable `MI CLAVE` -> mensaje generico en stderr, nada escrito, retorna `1`.
- Respuesta vacia en el correo -> mensaje generico en stderr, nada escrito, retorna `1`.
- `cancelar` como respuesta al proveedor -> mensaje generico con `cancelado` en stderr, nada escrito, retorna `1`.
- Entrada cerrada (EOF) durante la pregunta del correo -> mensaje generico con `cancelado` en stderr, nada escrito, retorna `1`.
- Setup con datos validos y `accounts.json` corrupto -> mensaje generico en stderr (sin `credential_ref`, sin traceback), retorna `1`.
- `cli_main(["account", "setup"])` y `cli_main(["account", "setup", "<root>", "extra"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "frobnicate", "<root>"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "add", "<root>", "legacy", "gmail", "x@y.com", "vault://k"])` y `cli_main(["search", "store", "correo"])` -> identicos a sus contratos ya congelados.

## Do / Don't

- Do: reutilizar el parseo ya existente de `cli_main` y agregar la rama `account setup` leyendo las respuestas con `input()` (una pregunta por llamada, en el orden congelado).
- Do: importar `create_email_account` desde `src.email.account` y `save_email_account` desde `src.email.account_store`, capturando sus errores para traducirlos al codigo `1`.
- Do: recortar cada respuesta con `strip()`, aceptar `cancelar`/`cancel` (insensible a mayusculas) en cualquier paso y tratar `EOFError`/`KeyboardInterrupt` como cancelacion.
- Do: construir `credential_ref` como `"env://" + NOMBRE` y pasarlo verbatim a `create_email_account`.
- Do: convertir cualquier `SystemExit` del parser en el codigo correspondiente y retornar siempre un `int`.
- Don't: pedir la contrasena (ni con `input` enmascarado, `getpass` ni lectura de la variable de entorno), resolver la credencial, conectarse a proveedores ni validar la clave durante el setup.
- Don't: imprimir `credential_ref`, el valor de la variable ni la contrasena en stdout, stderr o mensajes de error; los errores son genericos.
- Don't: mencionar OAuth ni ningun otro mecanismo de autenticacion en la ayuda, los prompts o los errores; el setup solo registra una referencia a una clave de aplicacion.
- Don't: reimplementar la creacion, validacion ni el guardado de cuentas dentro de la CLI; no usar red, `subprocess`, `eval` ni `exec`.
- Don't: alterar `search`, `account add/list`, `query`, `sync`, `draft` ni `send`, ni su salida ya congelada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_account_setup.py`.

```frozen-cases
[
  {
    "name": "help_shows_setup",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "account setup ROOT", "account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF", "search ROOT QUERY"],
    "stderr": []
  },
  {
    "name": "setup_success_gmail",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "Gmail", "Yo@Example.com", "GMAIL_APP_PASSWORD"],
    "code": 0,
    "stdout_has": ["cancelar", "Identificador de la cuenta", "Proveedor (gmail u outlook)", "Correo electronico", "variable de entorno"],
    "stdout_last": ["account saved: personal"],
    "stderr": [],
    "secrets": ["env://GMAIL_APP_PASSWORD"],
    "expect_store": {
      "account_id": "personal",
      "provider": "gmail",
      "email": "yo@example.com",
      "status": "disconnected"
    }
  },
  {
    "name": "setup_success_outlook",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["trabajo", "Outlook", "Trabajo@Example.com", "OUTLOOK_APP_PASSWORD"],
    "code": 0,
    "stdout_last": ["account saved: trabajo"],
    "stderr": [],
    "secrets": ["env://OUTLOOK_APP_PASSWORD"],
    "expect_store": {
      "account_id": "trabajo",
      "provider": "outlook",
      "email": "trabajo@example.com",
      "status": "disconnected"
    }
  },
  {
    "name": "setup_overwrites_existing_account",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "vieja@example.com", "credential_ref": "env://VIEJA", "status": "disconnected"}
    ],
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "outlook", "Nueva@Example.com", "NUEVA_CLAVE"],
    "code": 0,
    "stdout_last": ["account saved: personal"],
    "stderr": [],
    "secrets": ["env://NUEVA_CLAVE", "env://VIEJA"],
    "expect_store": {
      "account_id": "personal",
      "provider": "outlook",
      "email": "nueva@example.com",
      "status": "disconnected"
    }
  },
  {
    "name": "setup_provider_not_admitted",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "protonmail", "x@example.com", "CLAVE"],
    "code": 1,
    "stdout_has": ["Proveedor (gmail u outlook)"],
    "stderr_has": ["gmail", "outlook"],
    "secrets": ["env://CLAVE"]
  },
  {
    "name": "setup_env_var_name_invalid",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "gmail", "x@example.com", "MI CLAVE"],
    "code": 1,
    "stdout_has": ["variable de entorno"],
    "stderr_has": ["error"],
    "secrets": ["env://MI CLAVE"]
  },
  {
    "name": "setup_blank_email_answer",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "gmail", "   "],
    "code": 1,
    "stdout_has": ["Correo electronico"],
    "stderr_has": ["error"]
  },
  {
    "name": "setup_cancel_at_provider_prompt",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "cancelar"],
    "code": 1,
    "stdout_has": ["Proveedor (gmail u outlook)"],
    "stderr_has": ["cancelado"],
    "no_store": true
  },
  {
    "name": "setup_eof_at_email_prompt",
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "gmail"],
    "eof": true,
    "code": 1,
    "stdout_has": ["Correo electronico"],
    "stderr_has": ["cancelado"],
    "no_store": true
  },
  {
    "name": "setup_corrupt_store",
    "tree": {".email-agent/accounts.json": "{no es json"},
    "argv": ["account", "setup", "<root>"],
    "inputs": ["personal", "gmail", "x@example.com", "CLAVE_VALIDA"],
    "code": 1,
    "stdout_has": ["variable de entorno"],
    "stderr_has": ["error"],
    "secrets": ["env://CLAVE_VALIDA"]
  },
  {
    "name": "setup_missing_root_arg",
    "argv": ["account", "setup"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "setup_extra_args",
    "argv": ["account", "setup", "<root>", "extra"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "account_unknown_subcommand_preserved",
    "argv": ["account", "frobnicate", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "account_add_preserved",
    "argv": ["account", "add", "<root>", "legacy", "gmail", "x@y.com", "vault://gmail-legacy"],
    "code": 0,
    "stdout": ["account saved: legacy"],
    "stderr": [],
    "secrets": ["vault://gmail-legacy"],
    "expect_store": {
      "account_id": "legacy",
      "provider": "gmail",
      "email": "x@y.com",
      "status": "disconnected"
    }
  },
  {
    "name": "search_preserved",
    "tree": {
      "docs/guia.md": "Guia para BUSCAR correos rapidamente",
      "notes/inbox.md": "vamos a buscar el correo"
    },
    "argv": ["search", "<root>", "correo"],
    "code": 0,
    "stdout": ["docs/guia.md", "notes/inbox.md"],
    "stderr": []
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.account.create_email_account` con la firma `def create_email_account(account_id: str, provider: str, email: str, credential_ref: str) -> dict` y sobre `src.email.account_store.save_email_account` con la firma `def save_email_account(root: str, account: dict) -> str`, ambas locales y deterministas; los subcomandos `search ROOT QUERY`, `account add/list`, `query ROOT INSTRUCTION`, `sync ROOT ACCOUNT_ID [HOST]`, `draft ROOT ACCOUNT_ID TO SUBJECT BODY` y `send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR_ENVIO` deben quedar intactos sobre sus funciones ya congeladas. PARAR y reportar si el modulo `src.email.account` o la funcion `create_email_account` no existen con esa firma, si el modulo `src.email.account_store` o la funcion `save_email_account` no existen con esa firma, si algun subcomando ya congelado tuviera que cambiar de semantica, si hay que reimplementar la creacion, la validacion o el guardado de cuentas dentro de la CLI, si se tuviera que pedir la contrasena o el valor de la variable de entorno (en lugar de solo su NOMBRE), resolver la credencial o autenticar contra el proveedor durante el setup, si el `credential_ref` tuviera que construirse de otra forma que `"env://" + NOMBRE` o aparecer en stdout/stderr, si se necesitara afirmar OAuth u otro mecanismo de autenticacion, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, o si se necesitara red, `subprocess`, `getpass`, `eval` o `exec`.