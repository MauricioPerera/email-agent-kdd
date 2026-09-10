---
task: cli_search
intent: ejecutar la CLI local de correo con el subcomando search ROOT QUERY
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_search.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_search.py -q
deps_allowed: [argparse, sys]
forbids: [eval, exec, subprocess, network_access]
---
## Intent
Exponer la primera CLI local del agente de correo: interpretar `argv` (sin el nombre del programa), atender `--help` y el subcomando `search ROOT QUERY`, y comunicar el resultado por stdout con un codigo de retorno entero.

## Interface
`def cli_main(argv: list) -> int`

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe contener `usage:` y `search ROOT QUERY`) y retorna `0`.
- `search ROOT QUERY` (exactamente dos argumentos tras el subcomando): delega en `src.email.search.search_email_nodes(root, query)` e imprime cada ruta devuelta en su propia linea de stdout, en el orden recibido; retorna `0` (tambien cuando la lista viene vacia).
- Argumentos invalidos (argv vacio, primer argumento distinto de `search`/`--help`/`-h`, o `search` sin exactamente dos argumentos): imprime un mensaje amigable seguido del usage en stderr y retorna `2`.
- Fallo de la busqueda (cualquier excepcion lanzada por `search_email_nodes`): imprime un mensaje amigable en stderr y retorna `1`.

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- El codigo `0` solo corresponde a `--help`/`-h` y a `search` exitoso (con o sin coincidencias).
- El codigo `2` solo corresponde a errores de argumentos; el codigo `1` solo a fallos reportados por la busqueda.
- Los resultados se imprimen uno por linea, en el orden devuelto por `search_email_nodes`, sin reordenar, filtrar ni formatear.
- La busqueda no se reimplementa: la unica fuente de resultados es `src.email.search.search_email_nodes`.
- Los resultados van a stdout; usage y mensajes de error van a stderr.
- La funcion es determinista, no toca la red, no ejecuta procesos ni contenido leido y no modifica archivos.

## Examples

- `cli_main(["--help"])` -> imprime usage y retorna `0`.
- `cli_main(["search", "store", "correo"])` -> imprime `archive/lower.md` y `inbox/a.md` (una por linea) y retorna `0`.
- `cli_main(["search", "store", "factura pendiente"])` -> imprime `mail/b.md` y retorna `0`.
- `cli_main(["search", "store"])` -> mensaje amigable + usage en stderr y retorna `2`.
- `cli_main(["list", "todo"])` -> mensaje amigable + usage en stderr y retorna `2`.
- `cli_main(["search", "no-existe", "correo"])` -> mensaje amigable en stderr y retorna `1`.

## Do / Don't

- Do: usar `argparse` (o parseo manual equivalente) para reconocer `--help`, `-h` y `search ROOT QUERY`.
- Do: importar `search_email_nodes` desde `src.email.search` y capturar sus errores para traducirlos al codigo `1`.
- Do: escribir usage y errores en stderr, y resultados en stdout, un resultado por linea.
- Do: retornar siempre un `int` para que el llamador pueda usarlo como codigo de salida.
- Don't: reimplementar la busqueda (recorridos de archivos, filtrado por terminos) dentro de la CLI.
- Don't: dejar que `argparse` (u otro mecanismo) termine el proceso: convierte cualquier `SystemExit` en el codigo de retorno correspondiente.
- Don't: imprimir tracebacks ni detalles internos de la excepcion al usuario.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_search.py`.

```frozen-cases
[
  {
    "name": "help_shows_usage",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "search ROOT QUERY"],
    "stderr": []
  },
  {
    "name": "help_short_flag",
    "argv": ["-h"],
    "code": 0,
    "stdout_has": ["usage:"],
    "stderr": []
  },
  {
    "name": "search_single_term",
    "tree": {
      "docs/guia.md": "Guia para BUSCAR correos rapidamente",
      "docs/archivo.txt": "aqui hay correo pero no es markdown",
      "notes/inbox.md": "Hola mundo\nvamos a buscar el correo",
      "notes/outbox.md": "Nada relevante aqui"
    },
    "argv": ["search", "<root>", "correo"],
    "code": 0,
    "stdout": ["docs/guia.md", "notes/inbox.md"],
    "stderr": []
  },
  {
    "name": "search_and_terms",
    "tree": {
      "mail/a.md": "factura del correo electronico",
      "mail/b.md": "factura pendiente por el correo",
      "mail/c.md": "pendiente de revisar el correo",
      "mail/d.md": "FACTURA Pendiente CORREO"
    },
    "argv": ["search", "<root>", "factura pendiente correo"],
    "code": 0,
    "stdout": ["mail/b.md", "mail/d.md"],
    "stderr": []
  },
  {
    "name": "search_no_matches",
    "tree": {
      "solo.md": "contenido sin coincidencias utiles"
    },
    "argv": ["search", "<root>", "inexistente"],
    "code": 0,
    "stdout": [],
    "stderr": []
  },
  {
    "name": "search_missing_query",
    "tree": {
      "mail/a.md": "factura del correo electronico"
    },
    "argv": ["search", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "search_unknown_subcommand",
    "argv": ["list", "todo"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "search_bad_root",
    "tree": {
      "mail/a.md": "factura del correo electronico"
    },
    "argv": ["search", "<root>/faltante", "correo"],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "search_empty_query",
    "tree": {
      "mail/a.md": "factura del correo electronico"
    },
    "argv": ["search", "<root>", "   "],
    "code": 1,
    "stdout": [],
    "stderr_has": ["error"]
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.search.search_email_nodes` con la firma `def search_email_nodes(root: str, query: str) -> list`, local y determinista. PARAR y reportar si el modulo `src.email.search` o la funcion `search_email_nodes` no existen con esa firma, si hay que reimplementar la busqueda dentro de la CLI, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, si se necesita `argparse` y no esta disponible, o si hay que recurrir a red, subprocess, `eval` o `exec`.