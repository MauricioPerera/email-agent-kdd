---
task: cli_accounts
intent: extender la CLI local de correo con el subcomando account
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_accounts.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_accounts.py -q
deps_allowed: [argparse, sys, json]
forbids: [eval, exec, subprocess, network_access]
---
## Intent
Exponer la gestion amigable de cuentas en la CLI local de correo existente: atender el subcomando `account` (con `add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF` y `list ROOT`) ademas del `search ROOT QUERY` ya congelado, delegando la creacion, el guardado y la lectura en el modulo de cuentas y comunicando el resultado por stdout con un codigo de retorno entero.

## Interface
`def cli_main(argv: list) -> int` (misma funcion ya implementada para `search`; se extiende, no se reemplaza).

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe contener `usage:`, `account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF` y `search ROOT QUERY`) y retorna `0`.
- `account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF` (exactamente cinco argumentos tras el subcomando): construye el registro con `src.email.account.create_email_account(account_id, provider, email, credential_ref)`, lo persiste con `src.email.account_store.save_email_account(root, account)` e imprime en stdout unicamente la linea `account saved: ACCOUNT_ID` (account_id verbatim); retorna `0`.
- `account list ROOT` (exactamente un argumento tras el subcomando): carga con `src.email.account_store.load_email_accounts(root)` e imprime una linea JSON por cuenta en stdout, en el orden devuelto (ordenado por account_id); cada linea contiene solo `account_id`, `provider`, `email` y `status` (JSON con claves ordenadas), jamas `credential_ref`; retorna `0`, tambien `0` con lista vacia.
- Raiz ausente o archivo de cuentas ausente en `account list`: `load_email_accounts` devuelve `[]`, se imprime nada y retorna `0`.
- Errores de argumentos (argv vacio, primer argumento distinto de `search`/`account`/`--help`/`-h`, `account` sin subcomando conocido, o arity incorrecto en `account add`/`account list`/`search`): mensaje amigable seguido del usage en stderr, retorna `2`.
- Errores de almacenamiento/validacion (cualquier `ValueError` de `create_email_account` o `RuntimeError`/`ValueError` de `save_email_account`/`load_email_accounts`): mensaje generico amigable en stderr, retorna `1`.
- `search ROOT QUERY` conserva exactamente su semantica ya congelada en el contrato `cli_search` (delega en `src.email.search.search_email_nodes`, codigos `0`/`1`/`2`, una ruta por linea en stdout).

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- El codigo `0` solo corresponde a `--help`/`-h`, a `account add` exitoso, a `account list` exitoso (incluida la lista vacia) y a `search` exitoso.
- El codigo `2` solo corresponde a errores de argumentos; el codigo `1` solo a errores de almacenamiento/validacion.
- La creacion de la cuenta no se reimplementa: la unica fuente del registro es `src.email.account.create_email_account`.
- El guardado no se reimplementa: la unica via de persistencia es `src.email.account_store.save_email_account`.
- La lectura no se reimplementa: la unica fuente del listado es `src.email.account_store.load_email_accounts`.
- `credential_ref` jamas aparece en stdout ni en stderr de ningun comando; los mensajes de error son genericos (sin detalles de la excepcion, sin el valor de `credential_ref`, sin tracebacks).
- `account add` imprime en stdout exactamente una linea `account saved: ACCOUNT_ID` y nada mas.
- `account list` imprime una linea JSON por cuenta y nada mas; el JSON por linea no incluye `credential_ref` ni secretos.
- Los datos van a stdout; usage y mensajes de error van a stderr.
- La funcion es determinista, no toca la red, no ejecuta procesos ni contenido leido; la unica escritura en disco es la que hace `save_email_account` dentro del root indicado.
- La semantica existente de `search` no cambia en nada (mismo parseo, mismos codigos, misma salida).

## Examples

- `cli_main(["--help"])` -> imprime usage con `account add ...` y `search ROOT QUERY`, retorna `0`.
- `cli_main(["account", "add", "<root>", "personal", "Gmail", "Yo@Example.com", "vault://gmail"])` -> imprime `account saved: personal` y retorna `0`; queda `<root>/.email-agent/accounts.json` con el registro (provider `gmail`, email `yo@example.com`, status `disconnected`).
- `cli_main(["account", "list", "<root>"])` con dos cuentas guardadas -> imprime una linea JSON por cuenta (solo `account_id`, `provider`, `email`, `status`), ordenada por account_id, y retorna `0`.
- `cli_main(["account", "list", "<root>"])` con raiz sin store -> stdout vacio y retorna `0`.
- `cli_main(["account", "list"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "add", "<root>", "personal", "gmail"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "frobnicate", "<root>"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "add", "<root>", "personal", "   ", "x@y.com", "vault://k"])` -> mensaje generico en stderr (sin `credential_ref`, sin traceback), retorna `1`.
- `cli_main(["account", "add", "<root>", "personal", "gmail", "x@y.com", "vault://k"])` con `accounts.json` corrupto -> mensaje generico en stderr, retorna `1`.
- `cli_main(["account", "list", "<root>"])` con `accounts.json` corrupto -> mensaje generico en stderr, retorna `1`.
- `cli_main(["search", "store", "correo"])` -> identico al contrato `cli_search`: rutas en stdout y retorno `0`.

## Do / Don't

- Do: reutilizar el parseo ya existente de `cli_main` y agregar la rama `account` con `argparse` (o parseo manual equivalente).
- Do: importar `create_email_account` desde `src.email.account`, y `save_email_account`/`load_email_accounts` desde `src.email.account_store`, capturando sus errores para traducirlos al codigo `1`.
- Do: serializar cada cuenta listada con `json.dumps(..., sort_keys=True)` sobre solo las claves `account_id`, `provider`, `email` y `status`.
- Do: retornar siempre un `int` y convertir cualquier `SystemExit` del parser en el codigo correspondiente.
- Don't: reimplementar la creacion, validacion, guardado ni lectura de cuentas dentro de la CLI.
- Don't: imprimir `credential_ref` en stdout, en stderr ni en ningun mensaje de error (los errores son genericos).
- Don't: conectarse a proveedores, usar red, subprocess, `eval` o `exec`, ni loguear detalles internos de la excepcion.
- Don't: alterar el subcomando `search` ni su salida ya congelada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_accounts.py`.

```frozen-cases
[
  {
    "name": "help_shows_usage",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF", "search ROOT QUERY"],
    "stderr": []
  },
  {
    "name": "account_add_success",
    "argv": ["account", "add", "<root>", "personal", "Gmail", "Yo@Example.com", "vault://gmail-personal"],
    "code": 0,
    "stdout": ["account saved: personal"],
    "stderr": [],
    "secrets": ["vault://gmail-personal"],
    "expect_store": {
      "account_id": "personal",
      "provider": "gmail",
      "email": "yo@example.com",
      "status": "disconnected"
    }
  },
  {
    "name": "account_list_success",
    "store": [
      {"account_id": "a2", "provider": "outlook", "email": "b@example.com", "credential_ref": "vault://b", "status": "disconnected"},
      {"account_id": "a1", "provider": "gmail", "email": "a@example.com", "credential_ref": "vault://a", "status": "disconnected"}
    ],
    "argv": ["account", "list", "<root>"],
    "code": 0,
    "stdout": [
      "{\"account_id\": \"a1\", \"email\": \"a@example.com\", \"provider\": \"gmail\", \"status\": \"disconnected\"}",
      "{\"account_id\": \"a2\", \"email\": \"b@example.com\", \"provider\": \"outlook\", \"status\": \"disconnected\"}"
    ],
    "stderr": [],
    "secrets": ["vault://a", "vault://b", "credential_ref"]
  },
  {
    "name": "account_list_empty_root",
    "argv": ["account", "list", "<root>"],
    "code": 0,
    "stdout": [],
    "stderr": []
  },
  {
    "name": "account_list_missing_root_arg",
    "argv": ["account", "list"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "account_add_missing_args",
    "argv": ["account", "add", "<root>", "personal", "gmail"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "account_unknown_subcommand",
    "argv": ["account", "frobnicate", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "account_add_invalid_input",
    "argv": ["account", "add", "<root>", "personal", "   ", "x@y.com", "vault://k"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["vault://k"]
  },
  {
    "name": "account_add_corrupt_store",
    "tree": {".email-agent/accounts.json": "{no es json"},
    "argv": ["account", "add", "<root>", "personal", "gmail", "x@y.com", "vault://MARCADOR-SECRETO-123"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["vault://MARCADOR-SECRETO-123"]
  },
  {
    "name": "account_list_corrupt_store",
    "tree": {".email-agent/accounts.json": "{no es json"},
    "argv": ["account", "list", "<root>"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "search_semantics_preserved",
    "tree": {
      "docs/guia.md": "Guia para BUSCAR correos rapidamente",
      "notes/inbox.md": "vamos a buscar el correo"
    },
    "argv": ["search", "<root>", "correo"],
    "code": 0,
    "stdout": ["docs/guia.md", "notes/inbox.md"],
    "stderr": []
  },
  {
    "name": "search_arg_error_preserved",
    "argv": ["search", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.account.create_email_account` con la firma `def create_email_account(account_id: str, provider: str, email: str, credential_ref: str) -> dict`, sobre `src.email.account_store.save_email_account` con la firma `def save_email_account(root: str, account: dict) -> str` y sobre `src.email.account_store.load_email_accounts` con la firma `def load_email_accounts(root: str) -> list`, todas locales y deterministas; y sobre `src.email.search.search_email_nodes` con la firma `def search_email_nodes(root: str, query: str) -> list` cuyo subcomando `search` debe quedar intacto. PARAR y reportar si el modulo `src.email.account` o la funcion `create_email_account` no existen con esa firma, si el modulo `src.email.account_store` o las funciones `save_email_account`/`load_email_accounts` no existen con esas firmas, si el subcomando `search` ya congelado tuviera que cambiar de semantica, si hay que reimplementar la creacion, el guardado o la lectura de cuentas dentro de la CLI, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, si `credential_ref` (o cualquier secreto) tuviera que aparecer en stdout, en stderr o en un mensaje de error, si se necesitara red, subprocess, `eval` o `exec`, o si se tuviera que almacenar o leer el secreto real en lugar de la referencia opaca.