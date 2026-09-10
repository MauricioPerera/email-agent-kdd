---
task: cli_contact_list
intent: extender la CLI local de correo con el subcomando contact list ROOT que lista la libreta de contactos
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_contact_list.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_contact_list.py -q
deps_allowed: [argparse, sys, json, pathlib]
forbids: [eval, exec, subprocess, network_access]
---
## Intent
Exponer la libreta de contactos en la CLI local de correo existente: atender el subcomando `contact list ROOT` (exactamente un argumento ROOT tras `contact list`), delegando la lectura en `src.email.contact_store.load_email_contacts(root)` y comunicando el resultado por stdout con un codigo de retorno entero, sin alterar los subcomandos ya congelados `account`, `query`, `read`, `search`, `sync`, `draft` y `send`.

## Interface
`def cli_main(argv: list) -> int` (misma funcion ya implementada para `query`/`account`/`search`/`read`/`sync`/`draft`/`send`; se extiende, no se reemplaza).

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe seguir conteniendo las lineas de `query`, `search`, `read`, `account add`, `account setup`, `account list`, `sync`, `draft` y `send`, y ademas `contact list ROOT`) y retorna `0`.
- `contact list ROOT` (exactamente un argumento ROOT tras el subcomando `list`): carga con `src.email.contact_store.load_email_contacts(root)` e imprime una linea JSON por contacto en stdout, en el MISMO orden devuelto por la carga (el store lo deja ordenado por `email` ascendente); cada linea contiene SOLO las claves `name` y `email`; retorna `0`, tambien `0` con libreta vacia o store ausente.
- Store ausente (no existe `<root>/contacts.json`): `load_email_contacts` devuelve `[]`, se imprime nada y retorna `0`.
- Errores de almacenamiento/validacion (cualquier `ValueError` o `RuntimeError` de `load_email_contacts`): mensaje generico amigable en stderr, retorna `1`.
- Errores de argumentos (argv vacio, primer argumento distinto de `query`/`account`/`search`/`read`/`sync`/`draft`/`send`/`contact`/`--help`/`-h`, `contact` sin subcomando o con subcomando distinto de `list`, o arity incorrecto en `contact list` — cero argumentos o mas de uno): mensaje amigable seguido del usage en stderr, retorna `2`.
- Los subcomandos `account` (add/setup/list), `query`, `read`, `search`, `sync`, `draft` y `send` conservan exactamente su semantica ya congelada en los contratos `cli_accounts`, `cli_account_setup`, `cli_query`, `cli_search`, `cli_sync` y `cli-send` (mismo parseo, mismos codigos `0`/`1`/`2`, misma salida).

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- El codigo `0` solo corresponde a `--help`/`-h`, a `contact list` exitoso (incluida la lista vacia) y a los subcomandos preservados exitosos.
- El codigo `2` solo corresponde a errores de argumentos; el codigo `1` solo a errores de almacenamiento/validacion.
- La lectura no se reimplementa: la unica fuente del listado es `src.email.contact_store.load_email_contacts`.
- `contact list` imprime una linea JSON por contacto y nada mas; el JSON por linea tiene exactamente las claves `name` y `email`, jamas claves extra (`password`, `secret`, `token`, `credential_ref`) ni secretos.
- Los mensajes de error son genericos (sin detalles de la excepcion, sin contenido de las entradas, sin tracebacks); los datos van a stdout y usage/mensajes de error a stderr.
- La funcion es determinista, no toca la red, no ejecuta procesos ni contenido leido; `contact list` es de solo lectura: jamas crea `root`, ni `contacts.json`, ni `.tmp`, ni modifica nada.
- La semantica existente de `account`, `query`, `read`, `search`, `sync`, `draft` y `send` no cambia en nada (mismo parseo, mismos codigos, misma salida).

## Examples

- `cli_main(["--help"])` -> imprime usage con `contact list ROOT` y todos los subcomandos previos, retorna `0`.
- `cli_main(["contact", "list", "<root>"])` con dos contactos guardados -> imprime una linea JSON por contacto (solo `name` y `email`), en el orden devuelto por la carga, y retorna `0`.
- `cli_main(["contact", "list", "<root>"])` con raiz sin store -> stdout vacio y retorna `0`.
- `cli_main(["contact", "list"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["contact", "list", "<root>", "extra"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["contact", "frobnicate", "<root>"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["contact", "list", "<root>"])` con `contacts.json` corrupto -> mensaje generico en stderr (sin contenido de las entradas, sin traceback), retorna `1`.
- `cli_main(["contact", "list", ""])` -> mensaje generico en stderr, retorna `1` (`ValueError` de raiz vacia en el store).
- `cli_main(["search", "<root>", "correo"])` -> identico al contrato `cli_search`: rutas en stdout y retorno `0`.

## Do / Don't

- Do: reutilizar el parseo ya existente de `cli_main` y agregar la rama `contact` con `argparse` (o parseo manual equivalente).
- Do: importar `load_email_contacts` desde `src.email.contact_store`, capturando `ValueError`/`RuntimeError` para traducirlos al codigo `1`.
- Do: serializar cada contacto con `json.dumps({"name": ..., "email": ...})` (claves `name` y `email`, en el orden devuelto por la carga).
- Do: retornar siempre un `int` y convertir cualquier `SystemExit` del parser en el codigo correspondiente.
- Don't: reimplementar la lectura, validacion ni el esquema de contactos dentro de la CLI.
- Don't: imprimir claves extra, secretos, tokens ni contenido de entradas en stdout, en stderr ni en ningun mensaje de error (los errores son genericos).
- Don't: escribir, crear directorios, conectarse a proveedores, usar red, subprocess, `eval` o `exec`, ni loguear detalles internos de la excepcion.
- Don't: alterar los subcomandos `account`, `query`, `read`, `search`, `sync`, `draft` ni `send` ni su salida ya congelada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_contact_list.py`.

```frozen-cases
[
  {
    "name": "help_shows_usage",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "contact list ROOT", "search ROOT QUERY", "account list ROOT", "sync ROOT ACCOUNT_ID [HOST]"],
    "stderr": []
  },
  {
    "name": "contact_list_success",
    "store": [
      {"name": "Ana Garcia", "email": "ana@example.com"},
      {"name": "", "email": "bob@example.com"}
    ],
    "argv": ["contact", "list", "<root>"],
    "code": 0,
    "stdout": [
      "{\"name\": \"Ana Garcia\", \"email\": \"ana@example.com\"}",
      "{\"name\": \"\", \"email\": \"bob@example.com\"}"
    ],
    "stderr": []
  },
  {
    "name": "contact_list_preserves_file_order",
    "store": [
      {"name": "Zeta", "email": "zeta@example.com"},
      {"name": "Ana", "email": "ana@example.com"}
    ],
    "argv": ["contact", "list", "<root>"],
    "code": 0,
    "stdout": [
      "{\"name\": \"Zeta\", \"email\": \"zeta@example.com\"}",
      "{\"name\": \"Ana\", \"email\": \"ana@example.com\"}"
    ],
    "stderr": []
  },
  {
    "name": "contact_list_empty_root",
    "argv": ["contact", "list", "<root>"],
    "code": 0,
    "stdout": [],
    "stderr": []
  },
  {
    "name": "contact_list_missing_root_arg",
    "argv": ["contact", "list"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "contact_list_extra_args",
    "argv": ["contact", "list", "<root>", "extra"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "contact_bare",
    "argv": ["contact"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "contact_unknown_subcommand",
    "argv": ["contact", "frobnicate", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "unknown_subcommand",
    "argv": ["frobnicate"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "contact_list_corrupt_store",
    "tree": {"contacts.json": "{no es json"},
    "argv": ["contact", "list", "<root>"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "contact_list_out_of_schema",
    "tree": {"contacts.json": "{\"contacts\": [{\"name\": \"Ana\", \"email\": \"ana@example.com\", \"token\": \"MARCADOR-SECRETO-123\"}]}"},
    "argv": ["contact", "list", "<root>"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["MARCADOR-SECRETO-123"]
  },
  {
    "name": "contact_list_empty_root_value",
    "argv": ["contact", "list", ""],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"]
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.contact_store.load_email_contacts` con la firma `def load_email_contacts(root: str) -> list`, local y determinista: lee `<root>/contacts.json`, devuelve `[]` si el store no existe, lanza `ValueError` si `root` no es `str` no vacio y `RuntimeError` si el archivo esta corrupto o fuera del esquema exacto `name`/`email`, sin reordenar ni deduplicar. PARAR y reportar si el modulo `src.email.contact_store` o la funcion `load_email_contacts` no existen con esa firma, si el esquema devuelto difiere de las claves `name` y `email` documentadas aqui, si hay que reimplementar la lectura, la validacion o el esquema de contactos dentro de la CLI, si los subcomandos ya congelados `account`, `query`, `read`, `search`, `sync`, `draft` o `send` tuvieran que cambiar de semantica, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, si una clave extra o cualquier secreto tuviera que aparecer en stdout, en stderr o en un mensaje de error, si se necesitara escribir en disco, red, subprocess, `eval` o `exec`, o si los mensajes de error no pueden escribirse sin filtrar contenido de las entradas.