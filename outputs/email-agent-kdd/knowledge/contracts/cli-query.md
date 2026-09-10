---
task: cli_query
intent: ejecutar la CLI local de correo con el subcomando query ROOT INSTRUCTION
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_query.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_query.py -q
deps_allowed: [argparse, sys]
forbids: [eval, exec, subprocess, network_access]
---
## Intent
Exponer el subcomando `query ROOT INSTRUCTION` de la CLI local del agente de correo: interpretar `argv` (sin el nombre del programa), delegar la consulta en `src.email.query.query_email` y comunicar el resultado por stdout con un codigo de retorno entero.

## Interface
`def cli_main(argv: list) -> int` (la misma firma ya existente; se agrega el subcomando `query` sin tocar el resto).

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe contener `usage:`, `query ROOT INSTRUCTION` y seguir listando los subcomandos ya existentes `search`, `account`, `sync`, `draft` y `send`) y retorna `0`.
- `query ROOT INSTRUCTION` (exactamente dos argumentos tras el subcomando): `INSTRUCTION` llega como UN solo argumento de argv; si contiene espacios, la shell debe citarlo (p. ej. `email-cli query store "factura pendiente"`). Delega en `src.email.query.query_email(root, instruction)` e imprime cada ruta devuelta en su propia linea de stdout, en el orden recibido (la funcion ya devuelve las rutas ordenadas lexicograficamente, relativas y con separador `/`); retorna `0` (tambien cuando la lista viene vacia).
- Error de aridad o subcomando invalido (argv vacio, primer argumento distinto de los subcomandos reconocidos, o `query` con un numero de argumentos distinto de dos —incluido pasar la instruccion troceada en varios argumentos—): imprime un mensaje amigable seguido del usage en stderr y retorna `2`.
- Consulta invalida (`ValueError` lanzado por `query_email`: raiz inexistente o no directorio, instruccion vacia tras normalizar espacios, filtro `contact:`, `conversation:` o `topic:` malformado, o `.md` ilegible como UTF-8): imprime un mensaje amigable en stderr y retorna `2`.
- Cualquier otra excepcion de la consulta: imprime un mensaje amigable en stderr y retorna `1`.

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- El codigo `0` solo corresponde a `--help`/`-h` y a `query` exitoso (con o sin coincidencias).
- El codigo `2` solo corresponde a errores de aridad/subcomando y a consultas invalidas (`ValueError` de `query_email`); el codigo `1` solo a fallos inesperados reportados por la consulta.
- Los resultados se imprimen uno por linea, en el orden devuelto por `query_email`, sin reordenar, filtrar ni formatear.
- La consulta no se reinterpreta ni se reimplementa: la unica fuente de resultados es `src.email.query.query_email`; la CLI no tokeniza la instruccion ni conoce los filtros `contact:`/`conversation:`/`topic:`.
- `INSTRUCTION` se pasa completa como un solo argumento: la CLI no la divide ni la reconstruye.
- Los resultados van a stdout; usage y mensajes de error van a stderr, siempre genericos (sin secretos ni tracebacks).
- Los subcomandos ya existentes (`search ROOT QUERY`, `account add/list`, `sync`, `draft`, `send`) quedan intactos: mismos comportamientos, mismos codigos `0`/`1`/`2` y mismos mensajes; la unica adicion es `query` y su linea en el usage.
- La funcion es determinista, no toca la red, no ejecuta procesos ni contenido leido y no escribe archivos (la consulta es de solo lectura).

## Examples

- `cli_main(["--help"])` -> imprime usage con `query ROOT INSTRUCTION` y retorna `0`.
- `cli_main(["query", "store", "factura pendiente"])` -> imprime `store/emails/msg-0002.md` y retorna `0`.
- `cli_main(["query", "store", "topic:factura"])` -> imprime las rutas del indice del tema, ordenadas, y retorna `0`.
- `cli_main(["query", "store", "inexistente"])` -> no imprime nada y retorna `0`.
- `cli_main(["query", "store"])` -> mensaje amigable + usage en stderr y retorna `2`.
- `cli_main(["query", "store", "factura", "pendiente"])` -> la instruccion llego troceada: mensaje amigable + usage en stderr y retorna `2`.
- `cli_main(["query", "store", "   "])` -> mensaje amigable en stderr y retorna `2` (instruccion sin criterios).
- `cli_main(["query", "store", "topic:../etc"])` -> mensaje amigable en stderr y retorna `2` (filtro malformado).
- `cli_main(["query", "no-existe", "hola"])` -> mensaje amigable en stderr y retorna `2` (raiz invalida).
- `cli_main(["list", "todo"])` -> mensaje amigable + usage en stderr y retorna `2`.

## Do / Don't

- Do: reconocer `query` junto a los subcomandos ya existentes y exigir exactamente dos argumentos tras el subcomando.
- Do: importar `query_email` desde `src.email.query` y pasarle `(root, instruction)` tal cual llegaron por argv.
- Do: capturar `ValueError` de `query_email` para traducirlo al codigo `2` con mensaje amigable, y cualquier otra excepcion al codigo `1`.
- Do: escribir usage y errores en stderr, y resultados en stdout, un resultado por linea.
- Do: agregar la linea `query ROOT INSTRUCTION` al usage de `--help` sin alterar las lineas ya existentes.
- Don't: reimplementar la consulta (tokenizar la instruccion, aplicar filtros, recorrer archivos) dentro de la CLI.
- Don't: aceptar la instruccion troceada en varios argumentos ni unirla con espacios: si argv no trae exactamente dos argumentos tras `query`, es error de aridad.
- Don't: dejar que `argparse` (u otro mecanismo) termine el proceso: convierte cualquier `SystemExit` en el codigo de retorno correspondiente.
- Don't: tocar los subcomandos existentes ni imprimir tracebacks o detalles internos de la excepcion al usuario.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_query.py`.

```frozen-cases
[
  {
    "name": "help_shows_usage",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "query ROOT INSTRUCTION", "search ROOT QUERY", "account", "sync", "draft", "send"],
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
    "name": "query_free_terms_and",
    "tree": {
      "store/emails/msg-0001.md": "---\ntype: Email Message\nsubject: Hola\n---\nla factura del correo",
      "store/emails/msg-0002.md": "---\ntype: Email Message\nsubject: Re: Hola\n---\nfactura pendiente del correo",
      "store/emails/msg-0003.md": "---\ntype: Email Message\nsubject: Otro\n---\npendiente de revisar"
    },
    "argv": ["query", "<root>", "factura pendiente"],
    "code": 0,
    "stdout": ["store/emails/msg-0002.md"],
    "stderr": []
  },
  {
    "name": "query_casefold",
    "tree": {
      "store/emails/msg-0001.md": "---\ntype: Email Message\n---\nla FACTURA del correo",
      "store/emails/msg-0002.md": "---\ntype: Email Message\n---\nFactura pendiente",
      "store/emails/msg-0003.md": "---\ntype: Email Message\n---\nsin coincidencias aqui"
    },
    "argv": ["query", "<root>", "FACTURA"],
    "code": 0,
    "stdout": ["store/emails/msg-0001.md", "store/emails/msg-0002.md"],
    "stderr": []
  },
  {
    "name": "query_topic_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\ntype: Email Message\n---\ncuerpo uno",
      "store/emails/msg-0007.md": "---\ntype: Email Message\n---\ncuerpo dos",
      "store/emails/msg-0009.md": "---\ntype: Email Message\n---\ncuerpo tres",
      "store/topics/factura.md": "---\ntype: Topic\ntopic: factura\nmessage_count: 2\n---\n- store/emails/msg-0007.md\n- store/emails/msg-0001.md\n"
    },
    "argv": ["query", "<root>", "topic:factura"],
    "code": 0,
    "stdout": ["store/emails/msg-0001.md", "store/emails/msg-0007.md"],
    "stderr": []
  },
  {
    "name": "query_contact_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\nfrom: Ana Garcia <ANA@example.com>\nto: user@example.com\n---\nhola",
      "store/emails/msg-0002.md": "---\nfrom: Bob <bob@example.com>\n---\nhola de nuevo"
    },
    "argv": ["query", "<root>", "contact:ana@example.com"],
    "code": 0,
    "stdout": ["store/emails/msg-0001.md"],
    "stderr": []
  },
  {
    "name": "query_conversation_filter",
    "tree": {
      "store/emails/msg-0001.md": "cuerpo uno",
      "store/conversations/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md": "---\ntype: Conversation\nconversation_key: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nmessage_count: 1\n---\n- store/emails/msg-0001.md\n"
    },
    "argv": ["query", "<root>", "conversation:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"],
    "code": 0,
    "stdout": ["store/emails/msg-0001.md"],
    "stderr": []
  },
  {
    "name": "query_combined_and",
    "tree": {
      "store/emails/msg-0001.md": "---\nfrom: Ana Garcia <ana@example.com>\n---\nla factura",
      "store/emails/msg-0002.md": "---\nfrom: Bob <bob@example.com>\n---\nla factura",
      "store/emails/msg-0003.md": "---\nfrom: Ana Garcia <ana@example.com>\n---\nsin factura aqui",
      "store/topics/factura.md": "---\ntype: Topic\ntopic: factura\nmessage_count: 3\n---\n- store/emails/msg-0001.md\n- store/emails/msg-0002.md\n- store/emails/msg-0003.md\n"
    },
    "argv": ["query", "<root>", "contact:ana@example.com topic:factura factura"],
    "code": 0,
    "stdout": ["store/emails/msg-0001.md", "store/emails/msg-0003.md"],
    "stderr": []
  },
  {
    "name": "query_no_matches",
    "tree": {
      "store/emails/msg-0001.md": "contenido sin coincidencias utiles"
    },
    "argv": ["query", "<root>", "inexistente"],
    "code": 0,
    "stdout": [],
    "stderr": []
  },
  {
    "name": "query_missing_instruction",
    "tree": {
      "store/emails/msg-0001.md": "la factura del correo"
    },
    "argv": ["query", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "query_instruction_split_in_args",
    "tree": {
      "store/emails/msg-0001.md": "la factura pendiente del correo"
    },
    "argv": ["query", "<root>", "factura", "pendiente"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "query_unknown_subcommand",
    "argv": ["list", "todo"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "query_empty_instruction",
    "tree": {
      "store/emails/msg-0001.md": "la factura del correo"
    },
    "argv": ["query", "<root>", "   "],
    "code": 2,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "query_invalid_topic",
    "tree": {
      "store/emails/msg-0001.md": "la factura del correo"
    },
    "argv": ["query", "<root>", "topic:../etc"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "query_malformed_contact",
    "tree": {
      "store/emails/msg-0001.md": "la factura del correo"
    },
    "argv": ["query", "<root>", "contact:example.com"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["error"]
  },
  {
    "name": "query_bad_root",
    "tree": {
      "store/emails/msg-0001.md": "la factura del correo"
    },
    "argv": ["query", "<root>/faltante", "hola"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["error"]
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.query.query_email` con la firma `def query_email(root: str, instruction: str) -> list`, local y determinista. PARAR y reportar si el modulo `src.email.query` o la funcion `query_email` no existen con esa firma, si hay que reimplementar o reinterpretar la consulta dentro de la CLI, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, si agregar `query` exige modificar los subcomandos existentes (`search`, `account`, `sync`, `draft`, `send`) mas alla de anadir su linea al usage, si se necesita `argparse` y no esta disponible, o si hay que recurrir a red, subprocess, `eval` o `exec`.