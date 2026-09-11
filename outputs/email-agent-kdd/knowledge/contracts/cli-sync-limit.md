---
task: cli_sync_limit
intent: extender el subcomando sync de la CLI local de correo con la opcion --limit N para procesar una pagina IMAP limitada por ejecucion manteniendo la continuacion por cursor UID
target: ../../../../src/email/cli.py
signature: "def cli_main(argv: list) -> int"
test_cwd: ../../../..
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: ../../tests/frozen_cli_sync_limit.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_sync_limit.py -q
deps_allowed: [argparse, sys, json, pathlib]
forbids: [eval, exec, subprocess]
---
## Intent
Exponer la paginacion IMAP en la CLI local de correo existente: la opcion `--limit N` del subcomando `sync` fija el tamano de la pagina que `fetch_imap_messages` procesa en UNA ejecucion, la continuacion del buzon (miles de correos) se logra repitiendo el comando en ejecuciones posteriores apoyandose en el cursor UID ya congelado, y el uso actual sin la opcion conserva exactamente su semantica.

## Interface
`def cli_main(argv: list) -> int` (misma funcion ya implementada; se extiende, no se reemplaza). El frontmatter resuelve `target`, `tests` y `test_cwd` relativos a este contrato para que el gate verifique los archivos REALES del repo: `../../../../src/email/cli.py` es `src/email/cli.py` desde la raiz del repo y `test_cwd: ../../../..` es la raiz del repo.

Comportamiento de la rama `sync`:

- El usage (`USAGE` y `SYNC_USAGE`) documenta la forma `sync ROOT ACCOUNT_ID [HOST] [--limit N]`; los fragmentos ya congelados (`sync ROOT ACCOUNT_ID [HOST]`) siguen siendo subcadenas de esos textos.
- Antes de cualquier E/S, la rama `sync` extrae los pares `--limit N` de los tokens posteriores al subcomando (funcion auxiliar de la propia CLI, por ejemplo `_pop_sync_limit`):
  - `--limit` puede aparecer en cualquier posicion: antes de ROOT/ACCOUNT_ID, entre ellos y HOST, o al final.
  - `--limit` puede repetirse: el ultimo valor valido gana.
  - El valor debe ser un entero (texto parseable por `int`, sin signo razonable) en el rango 1..100 inclusive (constantes `LIMIT_MIN`/`LIMIT_MAX` de la propia CLI, espejo del rango de `fetch-imap-messages`).
  - `--limit` sin valor, con valor no numerico o fuera de 1..100: mensaje amigable seguido del usage en stderr, codigo `2`, CERO llamadas a fetch/persist/contactos, cero lecturas o escrituras de cursor y cero conexiones.
- El resto de tokens tras extraer `--limit` conserva la aridad ya congelada: ROOT y ACCOUNT_ID obligatorios, HOST opcional (3 o 4 tokens); cualquier otra aridad es error de argumentos con codigo `2`.
- Resolucion de cuenta, credencial, host (explicito o default por provider o servidores guardados), carga del cursor, `since_uid`, orquestacion via `sync_email_account`, persistencia OKF + indices + contactos y guardado del cursor: EXACTAMENTE la semantica ya congelada en el contrato `cli_sync` (mismos mensajes genericos, mismos codigos, mismas 5 claves del resumen).
- Config de fetch: `config = {"host": ..., "username": account["email"], "password": secreto, "since_uid": cursor}` y, SOLO si `--limit` esta presente, ademas `"limit": N` (int). Sin `--limit`, la config NO trae la clave `limit` y el default 50 (`DEFAULT_LIMIT` de `fetch-imap-messages`) aplica dentro del fetch, igual que hoy.
- El tamano de pagina NO lo valida la logica de negocio de la CLI contra el buzon: la CLI solo valida forma (entero 1..100); el recorte de la pagina (filtrar `id > since_uid`, ordenar ascendente y truncar a `limit`) sigue siendo responsabilidad exclusiva de `fetch_imap_messages`.

Paginacion y continuacion:

- Una ejecucion procesa a lo sumo UNA pagina de hasta `limit` mensajes nuevos (`imap_uid` > cursor); el cursor se guarda UNA vez con el MAXIMO `imap_uid` de la pagina persistida, solo si hubo records.
- La ejecucion siguiente carga el cursor y continua exactamente donde quedo: el filtro `id > since_uid` (estrictamente mayor) garantiza cero solapamiento y cero duplicados entre corridas.
- Si la bandeja no tiene mas mensajes nuevos que la pagina, `fetch` devuelve menos de `limit` (o vacia); con pagina vacia el cursor NO se escribe NI se avanza.
- La persistencia OKF es idempotente (`persist_email_okf_at` tolera reescritura con contenido identico y rechaza contenido distinto), asi que re-procesar registros tras un fallo previo al guardado del cursor no duplica nodos.
- `--limit` no altera el resumen: exactamente las 5 claves congeladas (`account_id`, `fetched`, `persisted`, `persisted_paths`, `contacts_updated`), sin claves nuevas ni renombradas; el valor del limite jamas aparece en stdout.

## Invariants

- `--limit` es una opcion de la capa de presentacion: la CLI jamas habla IMAP por su cuenta, jamas filtra ni trunca mensajes por su cuenta y jamas reimplementa `fetch_imap_messages`; el limite solo viaja como `config["limit"]` int.
- Sin `--limit`, la config de fetch no contiene la clave `limit` y la semantica congelada en `cli-sync` no cambia en nada (mismo argv, mismos codigos, misma salida, default 50 del fetch).
- El rango congelado del limite es 1..100 inclusive; `--limit 0`, `--limit 101`, `--limit abc`, `--limit -1` y `--limit` sin valor son error de argumentos (codigo `2` con usage), nunca error de operacion (codigo `1`).
- Un `--limit` invalido NO abre sesion IMAP (cero llamadas a fetch), NO toca el cursor (cero lecturas o guardados) y NO persiste nada.
- La continuacion entre ejecuciones sigue siendo exclusivamente el cursor UID via `load_sync_cursor`/`save_sync_cursor`: `since_uid` entra SIEMPRE en la config de fetch con el valor cargado, el cursor se guarda UNA vez tras un `sync_email_account` exitoso con el maximo `imap_uid` de los records y SOLO si hubo records; con pagina vacia el cursor queda intacto.
- Entre corridas no hay duplicados: el filtro `id > since_uid` de `fetch-imap-messages` y el guardado del maximo `imap_uid` de la pagina garantizan que un UID procesado no se reprocese.
- El resumen conserva exactamente sus 5 claves; `--limit` no agrega claves, no altera `persisted_paths` ni los conteos.
- `password`, el secreto resuelto y `credential_ref` jamas aparecen en stdout ni en stderr; los mensajes de error siguen siendo genericos (incluido el del `--limit` invalido, que no repite el valor en un contexto de secreto y no expone nada sensible).
- La sesion IMAP sigue siendo de solo lectura y ocurre dentro de `fetch_imap_messages`: la CLI no abre sockets ni habla protocolo.
- La semantica de `query`, `search`, `read`, `account`, `contact`, `draft` y `send` no cambia en nada.
- Codigos: `0` exito/ayuda, `1` fallo de operacion, `2` error de argumentos (incluidos los del `--limit`).

## Examples

- `cli_main(["sync", "<root>", "personal"])` con 60 mensajes nuevos y cursor 0 -> config SIN clave `limit`, el fetch aplica su default 50, resumen con `fetched: 50` y codigo `0` (uso actual intacto).
- `cli_main(["sync", "<root>", "personal", "--limit", "25"])` con 60 mensajes nuevos -> `config["limit"] == 25`, `fetched: 25`, los uids procesados son los primeros 25 mayores que el cursor en orden ascendente y el cursor se guarda con el maximo `imap_uid` de la pagina.
- `cli_main(["sync", "<root>", "personal", "imap.custom.test", "--limit", "3"])` -> host explicito y `config["limit"] == 3` en la misma ejecucion.
- `cli_main(["sync", "--limit", "2", "<root>", "personal"])` -> la opcion antes de ROOT/ACCOUNT_ID tambien se acepta y `config["limit"] == 2`.
- Tres ejecuciones consecutivas con `--limit 25`, `--limit 10` y sin `--limit` sobre un buzon de 60 mensajes nuevos -> procesan 1..25, 26..35 y 36..60 SIN duplicados, cada corrida arrancando del cursor UID guardado por la anterior.
- `cli_main(["sync", "<root>", "personal", "--limit", "5"])` con cursor 3 y bandeja sin mensajes nuevos -> `fetched: 0`, `persisted: 0`, el cursor NO se reescribe y queda `3`.
- `cli_main(["sync", "<root>", "personal", "--limit", "0"])`, `["--limit", "101"]`, `["--limit", "abc"]`, `["--limit", "-1"]` y `["--limit"]` (sin valor) -> mensaje amigable + usage en stderr, codigo `2`, cero llamadas a fetch/persist/contactos y cursor intacto.
- `cli_main(["sync", "<root>", "personal", "h", "extra"])` y `cli_main(["sync", "--limit", "10"])` -> codigo `2` con usage.
- `cli_main(["--help"])` -> usage que documenta `sync ROOT ACCOUNT_ID [HOST] [--limit N]`, codigo `0`.

## Do / Don't

- Do: extraer `--limit N` de los tokens del subcomando `sync` con una funcion auxiliar propia de la CLI antes de tocar cualquier E/S, aceptandola en cualquier posicion y con el ultimo valor valido como ganador.
- Do: pasar el limite a `fetch_imap_messages` UNICAMENTE como `config["limit"]` (int), solo cuando la opcion esta presente; sin la opcion, omitir la clave para que el fetch aplique su `DEFAULT_LIMIT` de 50.
- Do: validar el valor como entero 1..100 (`LIMIT_MIN`/`LIMIT_MAX`) en la CLI y rechazarlo con codigo `2` + usage antes de abrir conexion, cargar cursor o persistir nada.
- Do: conservar verbatim la semantica ya congelada de `cli-sync` (resolucion de cuenta/credencial/host, `since_uid`, orquestacion via `sync_email_account`, persistencia + indices + contactos, guardado del maximo `imap_uid` solo con records, resumen de 5 claves, codigos 0/1/2, secretos nunca impresos).
- Do: delegar el recorte de la pagina (filtro `id > since_uid`, orden ascendente, truncado a `limit`) en `fetch_imap_messages`; la CLI jamas recorta mensajes.
- Don't: validar el limite con E/S ya abierta (la validacion es previa a toda conexion), aceptar un `--limit` invalido como error de operacion (codigo `1`), reescribir el cursor con paginas vacias o reimplementar el fetch, el cursor o la orquestacion en la CLI.
- Don't: alterar `query`, `search`, `read`, `account`, `contact`, `draft` ni `send`; imprimir `password`, el secreto o `credential_ref`; usar subprocess, `eval` o `exec`; agregar claves al resumen por culpa del limite.

## Tests

Las propiedades congeladas estan en `tests/frozen_cli_sync_limit.py`. Oracle independiente de E/S: NO abre red real, NO usa credenciales reales, NO lanza procesos y NO toca disco de stores reales; inyecta dependencias falsas en el modulo `src.email.cli` (store de cuentas espejo, resolver de credenciales sobre environ ficticio, sesion IMAP simulada con filtro `id > since_uid` y recorte a `limit`, store de cursor espejo en memoria y orquestador de referencia con el mismo resumen de 5 claves). Congela: que la ayuda documente `sync ROOT ACCOUNT_ID [HOST] [--limit N]`, que sin `--limit` la config no fije `limit` (default 50 del fetch), que `--limit N` llegue a `fetch_imap_messages` via `config["limit"]`, la combinacion con HOST posicional, la aceptacion de `--limit` antes de ROOT/ACCOUNT_ID, la validacion 1..100 con codigo `2` sin tocar IMAP ni cursor, la aridad ya congelada de `sync`, la continuacion por cursor UID en multiples corridas sin duplicados y la pagina vacia sin reescribir el cursor.

```frozen-cases
[
  {"name": "help_documents_limit", "argv": ["--help"], "code": 0, "stdout_has": ["sync ROOT ACCOUNT_ID [HOST] [--limit N]"]},
  {"name": "default_omits_limit_key", "mailbox": 60, "argv": ["sync", "<root>", "personal"], "code": 0, "expected_limit": null, "fetched": 50, "cursor_saves": [["personal", 50]]},
  {"name": "limit_in_config", "mailbox": 60, "argv": ["sync", "<root>", "personal", "--limit", "25"], "code": 0, "expected_limit": 25, "fetched": 25, "cursor_saves": [["personal", 25]]},
  {"name": "limit_with_positional_host", "mailbox": 10, "argv": ["sync", "<root>", "personal", "imap.custom.test", "--limit", "3"], "code": 0, "expected_host": "imap.custom.test", "expected_limit": 3, "fetched": 3},
  {"name": "limit_before_positionals", "mailbox": 5, "argv": ["sync", "--limit", "2", "<root>", "personal"], "code": 0, "expected_limit": 2, "fetched": 2},
  {"name": "resume_without_duplicates", "mailbox": 60, "runs": [["--limit", "25"], ["--limit", "10"], []], "code": 0, "expected_no_duplicates": true},
  {"name": "empty_page_keeps_cursor", "mailbox": 3, "cursor": 3, "argv": ["sync", "<root>", "personal", "--limit", "5"], "code": 0, "fetched": 0, "cursor_saves": []},
  {"name": "limit_zero_is_argument_error", "argv": ["sync", "<root>", "personal", "--limit", "0"], "code": 2, "fetch_calls": 0},
  {"name": "limit_over_max_is_argument_error", "argv": ["sync", "<root>", "personal", "--limit", "101"], "code": 2, "fetch_calls": 0},
  {"name": "limit_non_numeric_is_argument_error", "argv": ["sync", "<root>", "personal", "--limit", "abc"], "code": 2, "fetch_calls": 0},
  {"name": "limit_negative_is_argument_error", "argv": ["sync", "<root>", "personal", "--limit", "-1"], "code": 2, "fetch_calls": 0},
  {"name": "limit_without_value_is_argument_error", "argv": ["sync", "<root>", "personal", "--limit"], "code": 2, "fetch_calls": 0},
  {"name": "extra_args_still_argument_error", "argv": ["sync", "<root>", "personal", "h", "extra"], "code": 2},
  {"name": "limit_alone_is_argument_error", "argv": ["sync", "--limit", "10"], "code": 2}
]
```

## Constraints

La CLI debe permanecer una capa fina sobre `src.email.account_store.load_email_accounts` con la firma `def load_email_accounts(root: str) -> list`, sobre `src.email.mail_server_store.load_mail_server_config`, sobre `src.email.credentials.resolve_credential` con la firma `def resolve_credential(credential_ref: str, environ=None) -> str`, sobre `src.email.cursor_store.load_sync_cursor` con la firma `def load_sync_cursor(root: str, account_id: str) -> int`, sobre `src.email.cursor_store.save_sync_cursor` con la firma `def save_sync_cursor(root: str, account_id: str, uid: int) -> str`, sobre `src.email.imap_reader.fetch_imap_messages` con la firma `def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list`, sobre `src.email.sync.sync_email_account` con la firma `def sync_email_account(account: dict, fetch_messages, persist_message, update_contacts=None) -> dict`, sobre `src.email.persist_at.persist_email_okf_at` con la firma `def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`, sobre `src.email.conversation_index.persist_conversation_index`, sobre `src.email.topic_index.persist_topic_index`, sobre `src.email.contacts.extract_contacts` con la firma `def extract_contacts(record: dict) -> list` y sobre `src.email.contact_store.store_email_contacts` con la firma `def store_email_contacts(root: str, contacts: list) -> int`, todas delegadas y jamas reimplementadas dentro de la CLI; el limite viaja UNICAMENTE como `config["limit"]` int hacia `fetch_imap_messages`, el recorte de la pagina (filtro `id > since_uid`, orden ascendente, truncado) es responsabilidad exclusiva de `fetch-imap-messages`, la continuacion entre ejecuciones es exclusivamente el cursor UID ya congelado (`load_sync_cursor` antes del fetch, `save_sync_cursor` UNA vez con el maximo `imap_uid` solo con records), la validacion del valor de `--limit` (entero 1..100) es previa a toda E/S y su rechazo es error de argumentos con codigo `2`, sin `--limit` la config no trae la clave `limit` y la semantica de `cli-sync` queda intacta (mismo default 50 del fetch, mismas 5 claves del resumen, mismos codigos 0/1/2 y separacion stdout/stderr), `password`, el secreto resuelto y `credential_ref` jamas aparecen en stdout ni en stderr, la sesion IMAP sigue siendo de solo lectura y ocurre dentro de `fetch_imap_messages`, y los subcomandos `query`, `search`, `read`, `account`, `contact`, `draft` y `send` no cambian en nada. PARAR y reportar si el modulo o la funcion de cualquiera de esas dependencias no existen con esa firma, si hay que reimplementar el fetch IMAP, el cursor o la orquestacion dentro de la CLI, si `--limit` no pudiera validarse antes de toda E/S o su rechazo no pudiera ser codigo `2` con usage, si el limite no pudiera viajar como `config["limit"]` int solo cuando la opcion esta presente (o sin la opcion la config tuviera que traer la clave), si la continuacion entre ejecuciones necesitara algo distinto del cursor UID ya congelado, si un UID procesado pudiera reprocesarse (duplicados entre corridas), si con pagina vacia el cursor tuviera que escribirse o avanzarse, si el resumen tuviera que ganar o cambiar claves por culpa del limite, si `password`, el secreto o `credential_ref` pudieran aparecer en la salida, si la sesion IMAP tuviera que abrirse fuera de `fetch_imap_messages` o en modo distinto de solo lectura, si los subcomandos ya congelados tuvieran que cambiar de semantica, si no se pudieran respetar los codigos 0/1/2, o si se necesitara subprocess, `eval` o `exec`.