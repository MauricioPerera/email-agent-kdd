---
task: cli_sync
intent: extender la CLI local de correo con el subcomando sync que sincroniza una cuenta guardada con cursor incremental
target: src/email/cli.py
signature: "def cli_main(argv: list) -> int"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_cli_sync.py
test_command: python -m pytest outputs/email-agent-kdd/tests/frozen_cli_sync.py -q
deps_allowed: [argparse, sys, json, pathlib]
forbids: [eval, exec, subprocess]
---
## Intent
Exponer la sincronizacion en la CLI local de correo existente: atender el subcomando `sync ROOT ACCOUNT_ID [HOST]` ademas de `search ROOT QUERY` y `account`, resolviendo la cuenta guardada, la credencial via su referencia, el host IMAP y el cursor incremental de la cuenta, orquestando la lectura IMAP, la persistencia OKF, la indexacion de conversaciones, la actualizacion de contactos y el avance del cursor tras un sync exitoso, con un resumen JSON en stdout y un codigo de retorno entero.

## Interface
`def cli_main(argv: list) -> int` (misma funcion ya implementada para `search` y `account`; se extiende, no se reemplaza).

Comportamiento:

- `--help` o `-h` como primer argumento: imprime el usage en stdout (debe contener `usage:`, `search ROOT QUERY`, `account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF`, `account list ROOT` y `sync ROOT ACCOUNT_ID [HOST]`) y retorna `0`.
- `sync ROOT ACCOUNT_ID [HOST]` (exactamente tres o cuatro argumentos tras el subcomando), en orden:
  1. Carga las cuentas con `src.email.account_store.load_email_accounts(root)` y selecciona la cuenta cuyo `account_id` sea exactamente ACCOUNT_ID. Sin esa cuenta: mensaje generico en stderr, `0` llamadas a fetch/persist/contactos y retorna `1`.
  2. Resuelve la credencial UNICAMENTE mediante `src.email.credentials.resolve_credential(account["credential_ref"])`: el secreto vive solo en memoria. Fallo (`ValueError`): mensaje generico en stderr (sin `credential_ref`, sin el nombre de la variable, sin secretos), cero llamadas posteriores y retorna `1`.
  3. Resuelve el host: si HOST viene en argv se usa verbatim; si no, el default del provider de la cuenta (`gmail` -> `imap.gmail.com`, `outlook` -> `outlook.office365.com`). Provider sin default y sin HOST: mensaje generico en stderr, cero conexiones y retorna `1`.
  4. Carga el cursor incremental de la cuenta ANTES del fetch, UNICAMENTE via `src.email.cursor_store.load_sync_cursor(root, account_id)` (firma `def load_sync_cursor(root: str, account_id: str) -> int`; devuelve `0` si no hay entrada, la ausencia no es error). Fallo (`ValueError` o `RuntimeError`, incluido un `cursors.json` corrupto): mensaje generico en stderr (sin secretos), cero llamadas a fetch/persist/contactos, ninguna escritura y retorna `1`.
  5. Construye `config = {"host": host, "username": account["email"], "password": secreto, "since_uid": cursor}`: `since_uid` (int) entra SIEMPRE en la config de fetch con el valor cargado.
  6. Orquesta con `src.email.sync.sync_email_account(account, fetch, persist, update_contacts)` donde:
     - `fetch(account)` llama `src.email.imap_reader.fetch_imap_messages(account, config)` (una sola sesion IMAP de solo lectura por ejecucion) y DEVUELVE verbatim la lista de records obtenida para que la CLI disponga de ella tras el sync; cada record garantiza la clave `imap_uid` (int, nunca `str` ni `bool`) segun el contrato `fetch-imap-messages`, y el filtrado `id > since_uid` es responsabilidad exclusiva de `fetch_imap_messages`, jamas de la CLI;
     - `persist(record)` llama PRIMERO `src.email.persist_at.persist_email_okf_at(record, root, "store/emails/" + record["raw_sha256"] + ".md")` (firma `def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`; el `rel_path` `store/emails/<raw_sha256>.md` es RELATIVO al root y se deriva del hash del registro), DESPUES `src.email.conversation_index.persist_conversation_index(root, record, rel_path)` (firma `def persist_conversation_index(root: str, record: dict, message_path: str) -> str`) y LUEGO `src.email.topic_index.persist_topic_index(root, record, rel_path)` (firma `def persist_topic_index(root: str, record: dict, message_path: str) -> int`), en ese orden y siempre con el mismo `rel_path` recien persistido como `message_path`; el callback devuelve la ruta del mensaje, es decir el valor de retorno de `persist_email_okf_at`, que es lo que alimenta `persisted_paths`; el retorno `int` de `persist_topic_index` (numero de temas procesados) se descarta y no entra en ninguna salida;
     - `update_contacts(messages)` (siempre presente en esta rama) aplica `src.email.contacts.extract_contacts` a cada registro en orden, fusiona los contactos resultantes en una sola lista deduplicando por email en minusculas (la primera aparicion gana su `name`) y llama UNA sola vez al final a `src.email.contact_store.store_email_contacts(root, contacts)` con la firma `def store_email_contacts(root: str, contacts: list) -> int`.
  7. Tras un `sync_email_account` exitoso, guarda el cursor UNA sola vez y SOLO si la lista de records devuelta por `fetch` NO esta vacia: `src.email.cursor_store.save_sync_cursor(root, account_id, max(record["imap_uid"] para los records))` (firma `def save_sync_cursor(root: str, account_id: str, uid: int) -> str`; su retorno `str` se descarta). Con bandeja vacia (`fetched: 0`) el cursor NO se escribe NI se avanza. Fallo del guardado (`ValueError` o `RuntimeError`): mensaje generico en stderr (sin secretos), nada en stdout y retorna `1`. El guardado ocurre DESPUES de `sync_email_account` y ANTES de imprimir el resumen, y no altera ni el resumen ni el orden de persistencia. Luego imprime en stdout EXACTAMENTE una linea `json.dumps(resumen, sort_keys=True)` (claves `account_id`, `fetched`, `persisted`, `persisted_paths`, `contacts_updated`) y retorna `0`, tambien con bandeja vacia (`fetched: 0`, `persisted: 0`, `persisted_paths: []`, `contacts_updated: true`). La indexacion de conversaciones y de temas y el guardado del cursor NO alteran el resumen: `persisted_paths` sigue siendo solo la lista de rutas de mensajes (NO incluye rutas de indices de conversaciones, de temas ni del cursor), y no se agregan ni renombran claves.
- Errores de argumentos (argv vacio, primer argumento distinto de `sync`/`search`/`account`/`--help`/`-h`, o `sync` con arity distinto de 3/4 tras el subcomando): mensaje amigable seguido del usage en stderr, retorna `2`.
- Errores de operacion (store corrupto o ilegible, cuenta ausente, `ValueError` de `resolve_credential`, provider sin host por defecto, fallo de carga o de guardado del cursor (`ValueError`/`RuntimeError` de `load_sync_cursor`/`save_sync_cursor`, incluido un `cursors.json` corrupto), o `RuntimeError`/`ValueError` lanzados por `fetch_imap_messages`, la persistencia (OKF, indice de conversaciones o indice de temas) o `update_contacts` envueltos por `sync_email_account`): mensaje generico amigable en stderr, retorna `1`.
- `search ROOT QUERY` y `account` conservan exactamente su semantica ya congelada en los contratos `cli_search` y `cli_accounts`.

## Invariants

- `cli_main` nunca deja escapar excepciones hacia el llamador: toda falla se traduce a un codigo distinto de cero y un mensaje amigable en stderr, sin traceback.
- El codigo `0` solo corresponde a `--help`/`-h` y a `sync` exitoso (con o sin mensajes nuevos).
- El codigo `2` solo corresponde a errores de argumentos; el codigo `1` solo a errores de operacion (cuenta ausente, credencial irresoluble, provider sin host, fallo de store, fallo IMAP, fallo de persistencia OKF, de indice de conversaciones, de indice de temas, de contactos o de cursor, en carga o en guardado).
- La cuenta no se resuelve reimplementando el store: la unica fuente es `src.email.account_store.load_email_accounts`.
- El secreto se obtiene UNICAMENTE via `src.email.credentials.resolve_credential(account["credential_ref"])`: la CLI jamas lee variables de entorno por su cuenta, jamas guarda ni persiste el secreto, y jamas lo imprime.
- `password` y `credential_ref` jamas aparecen en stdout ni en stderr de ningun comando; el resumen y los mensajes de error son genericos.
- La sesion IMAP es de solo lectura y ocurre dentro de `fetch_imap_messages`: la CLI no abre sockets ni habla protocolo por su cuenta.
- El cursor incremental se lee ANTES del fetch y UNICAMENTE via `src.email.cursor_store.load_sync_cursor(root, account_id)` (firma `def load_sync_cursor(root: str, account_id: str) -> int`): `0` si no hay entrada, y la ausencia del archivo no es error; la CLI jamas lee ni escribe `.email-agent/cursors.json` por su cuenta ni reimplementa el store de cursor.
- `since_uid` entra SIEMPRE en la config de fetch con el valor cargado (int); el filtrado `id > since_uid` (estrictamente mayor, antes de ordenar y truncar) es responsabilidad exclusiva de `fetch_imap_messages`, jamas de la CLI.
- El callback `fetch` devuelve verbatim la lista de records obtenida por `fetch_imap_messages`; cada record garantiza `imap_uid` (int, nunca `str` ni `bool`) segun el contrato `fetch-imap-messages`.
- El cursor se guarda UNA sola vez por ejecucion, DESPUES de un `sync_email_account` exitoso y ANTES de imprimir el resumen, UNICAMENTE via `src.email.cursor_store.save_sync_cursor(root, account_id, uid)` (firma `def save_sync_cursor(root: str, account_id: str, uid: int) -> str`, retorno `str` descartado) y SOLO si hubo records: el uid guardado es el MAXIMO `imap_uid` de los records obtenidos; con bandeja vacia el cursor NO se escribe NI se avanza ni se reinicia.
- Un fallo de cursor (carga o guardado, `ValueError` o `RuntimeError`, incluido `cursors.json` corrupto) es un error operativo: mensaje generico amigable en stderr SIN secretos, codigo `1` y nada en stdout; la carga fallida ocurre antes del fetch (cero llamadas) y la fallida de guardado no imprime el resumen.
- El guardado del cursor no altera la salida: el resumen conserva exactamente sus 5 claves, `persisted_paths` no incluye ninguna ruta de cursor y el retorno `str` de `save_sync_cursor` se descarta.
- Cada mensaje se persiste una sola vez en `store/emails/<raw_sha256>.md` (rel_path relativo al root) via `persist_email_okf_at(record, root, rel_path)`; `persisted_paths` del resumen conserva el orden de persistencia.
- Cada mensaje persistido dispara la indexacion de su conversacion via `persist_conversation_index(root, record, rel_path)`, SIEMPRE despues de que el mensaje ya fue escrito por `persist_email_okf_at` y con el mismo `rel_path` como `message_path`; el indice de cada conversacion queda en `root/store/conversations/<conversation_key>.md` (relativo al root), responsabilidad exclusiva de `src.email.conversation_index`.
- La indexacion de conversaciones es un efecto secundario de la persistencia y NO altera la salida: el resumen conserva exactamente las 5 claves, `persisted` cuenta solo mensajes y `persisted_paths` contiene solo rutas de mensajes bajo `store/emails/`, jamas rutas de indices bajo `store/conversations/`.
- Cada mensaje persistido dispara tambien la indexacion de sus temas via `persist_topic_index(root, record, rel_path)` (firma `def persist_topic_index(root: str, record: dict, message_path: str) -> int`), SIEMPRE despues de `persist_email_okf_at` y de `persist_conversation_index` y con el mismo `rel_path` como `message_path`; los nodos de tema quedan en `root/store/topics/<topic>.md` (relativo al root), responsabilidad exclusiva de `src.email.topic_index`; su retorno `int` se descarta.
- La indexacion de temas es otro efecto secundario de la persistencia y TAMPOCO altera la salida: ni claves nuevas en el resumen, ni `persisted_paths` con rutas bajo `store/topics/`, ni conteos distintos de mensajes persistidos.
- Los contactos se derivan via `extract_contacts` (From, To, Cc), se fusionan con dedupe por email en minusculas y se delegan en `store_email_contacts(root, contacts)` UNA vez por ejecucion, despues de persistir los mensajes.
- Los datos van a stdout (exactamente una linea JSON); usage y errores a stderr.
- La semantica existente de `search` y `account` no cambia en nada (mismo parseo, mismos codigos, misma salida).
- La funcion es determinista en su capa: la unica E/S de red es la que hace `fetch_imap_messages` y las unicas escrituras en disco son las que hacen `persist_email_okf_at`, `persist_conversation_index`, `persist_topic_index`, `store_email_contacts` y `save_sync_cursor`, siempre dentro del root indicado.

## Examples

- `cli_main(["--help"])` -> imprime usage con `search ROOT QUERY`, `account ...` y `sync ROOT ACCOUNT_ID [HOST]`, retorna `0`.
- `cli_main(["sync", "<root>", "personal", "imap.custom.test"])` con cuenta `personal` (provider `gmail`, credential_ref `env://EMAIL_PASSWORD`) guardada y la variable presente -> una linea JSON en stdout con `{"account_id": "personal", "fetched": 2, "persisted": 2, "persisted_paths": ["store/emails/a1a1a1a1.md", "store/emails/b2b2b2b2.md"], "contacts_updated": true}` y retorna `0`; el host usado es `imap.custom.test`, el cursor se carga antes del fetch (`0` si no hay entrada) y `since_uid: 0` entra en la config, quedan escritos `<root>/store/emails/a1a1a1a1.md` y `<root>/store/emails/b2b2b2b2.md` via `persist_email_okf_at` con rel_paths relativos al root, cada mensaje dispara despues `persist_conversation_index(root, record, rel_path)` dejando su indice en `<root>/store/conversations/<conversation_key>.md` (que NO aparece en `persisted_paths`), los contactos deduplicados se delegan UNA vez a `store_email_contacts(root, contacts)` y, tras el exito, el cursor se guarda UNA vez con el maximo `imap_uid` de los records dejando `<root>/.email-agent/cursors.json` (que NO aparece en `persisted_paths`).
- `cli_main(["sync", "<root>", "personal"])` con provider `gmail` -> usa `imap.gmail.com` como host y retorna `0` con el resumen JSON.
- `cli_main(["sync", "<root>", "work"])` con provider `outlook` -> usa `outlook.office365.com` como host y retorna `0` con el resumen JSON.
- `cli_main(["sync", "<root>", "inexistente"])` con store sin esa cuenta -> mensaje generico en stderr, ningun mensaje obtenido ni persistencia ni contactos, retorna `1`.
- `cli_main(["sync", "<root>", "personal"])` con `credential_ref` apuntando a una variable de entorno ausente -> mensaje generico en stderr (sin `credential_ref` ni nombre de variable), ningun mensaje obtenido, retorna `1`.
- `cli_main(["sync", "<root>", "personal"])` con provider `unknown` sin HOST -> mensaje generico en stderr (sin host por defecto), ninguna conexion, retorna `1`.
- `cli_main(["sync", "<root>", "personal"])` cuando la lectura IMAP falla -> mensaje generico en stderr, nada persistido, contactos no llamados, retorna `1`.
- `cli_main(["sync"])` y `cli_main(["sync", "<root>"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["sync", "<root>", "personal", "imap.x", "extra"])` -> mensaje amigable + usage en stderr, retorna `2`.
- `cli_main(["account", "list", "<root>"])` y `cli_main(["search", "store", "correo"])` -> identicos a sus contratos ya congelados.
- `cli_main(["sync", "<root>", "personal"])` sin `<root>/.email-agent/cursors.json` y records con `imap_uid` `41` y `57` -> cursor cargado `0`, `since_uid: 0` en la config, ambos mensajes procesados y, tras el exito, `save_sync_cursor(root, "personal", 57)` escribe `<root>/.email-agent/cursors.json` con `{"cursors": {"personal": 57}}`; resumen JSON y `0` (el archivo de cursor NO aparece en `persisted_paths`).
- `cli_main(["sync", "<root>", "personal"])` con `<root>/.email-agent/cursors.json` `{"cursors": {"personal": 100}}` y records con `imap_uid` `100` y `101` -> cursor cargado `100`, `since_uid: 100` en la config, `fetch_imap_messages` devuelve solo los records con `imap_uid > 100` (el `100` queda descartado por el filtro de `fetch-imap-messages`), `fetched: 1`, `persisted: 1` y el cursor se guarda con `101`.
- `cli_main(["sync", "<root>", "personal"])` con cursor `{"cursors": {"personal": 30}}` y bandeja vacia -> `since_uid: 30` en la config, `fetch_imap_messages` devuelve `[]`, resumen con `fetched: 0`, `persisted: 0`, `persisted_paths: []`, `contacts_updated: true`, `store_email_contacts` recibe la lista vacia, `save_sync_cursor` NO se llama y el cursor queda `30` sin avanzar.
- `cli_main(["sync", "<root>", "personal"])` con `<root>/.email-agent/cursors.json` corrupto (no es JSON o esquema invalido) -> `load_sync_cursor` lanza `RuntimeError`, mensaje generico en stderr (sin secretos), cero llamadas a fetch/persist/contactos y retorna `1`.

## Do / Don't

- Do: reutilizar el parseo ya existente de `cli_main` y agregar la rama `sync` con `argparse` (o parseo manual equivalente).
- Do: importar y delegar en `load_email_accounts` (src.email.account_store), `resolve_credential` (src.email.credentials), `fetch_imap_messages` (src.email.imap_reader), `sync_email_account` (src.email.sync), `persist_email_okf_at` (src.email.persist_at, firma `def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`), `persist_conversation_index` (src.email.conversation_index, firma `def persist_conversation_index(root: str, record: dict, message_path: str) -> str`), `persist_topic_index` (src.email.topic_index, firma `def persist_topic_index(root: str, record: dict, message_path: str) -> int`), `extract_contacts` (src.email.contacts) y `store_email_contacts` (src.email.contact_store, firma `def store_email_contacts(root: str, contacts: list) -> int`), capturando sus errores para traducirlos al codigo `1`.
- Do: hacer que el callback `persist` llame PRIMERO a `persist_email_okf_at(record, root, rel_path)`, DESPUES a `persist_conversation_index(root, record, rel_path)` y LUEGO a `persist_topic_index(root, record, rel_path)`, siempre con el mismo rel_path, devolviendo la ruta del mensaje (el retorno de `persist_email_okf_at`), que es lo unico que entra en `persisted_paths`; el `int` de `persist_topic_index` se descarta.
- Do: pasar a `persist_email_okf_at` SIEMPRE una ruta relativa (`"store/emails/" + record["raw_sha256"] + ".md"`) junto al root, jamas una ruta absoluta; el indice de la conversacion lo escribe `persist_conversation_index` en `store/conversations/<conversation_key>.md` y los nodos de tema los escribe `persist_topic_index` en `store/topics/<topic>.md`, nunca la CLI.
- Do: resolver el host con el mapa de defaults `{"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}` y permitir que HOST en argv lo reemplace verbatim.
- Do: cargar el cursor ANTES del fetch via `load_sync_cursor(root, account_id)` (firma `def load_sync_cursor(root: str, account_id: str) -> int`), tratar su `0` como primera sincronizacion (sin entrada no hay error) y meter ese valor como `since_uid` int en la config de fetch.
- Do: conservar verbatim la lista de records que devuelve el callback `fetch` (cada record garantiza `imap_uid` int segun `fetch-imap-messages`) y, si `sync_email_account` fue exitoso y la lista NO esta vacia, guardar UNA vez el MAXIMO `imap_uid` via `save_sync_cursor(root, account_id, max_uid)` (firma `def save_sync_cursor(root: str, account_id: str, uid: int) -> str`, retorno descartado), DESPUES del sync y ANTES de imprimir el resumen; con bandeja vacia NO guardar ni avanzar el cursor.
- Do: traducir cualquier `ValueError`/`RuntimeError` de `load_sync_cursor` o `save_sync_cursor` a mensaje generico en stderr con codigo `1`, sin secretos.
- Do: imprimir el resumen como una unica linea `json.dumps(..., sort_keys=True)` en stdout.
- Do: retornar siempre un `int` y convertir cualquier `SystemExit` del parser en el codigo correspondiente.
- Don't: reimplementar la lectura de cuentas, la resolucion de credenciales, el fetch IMAP, la orquestacion, la persistencia OKF, la indexacion de conversaciones, la indexacion de temas ni la extraccion/fusion de contactos dentro de la CLI.
- Don't: escribir directamente archivos de indice de conversaciones ni de temas, calcular el `conversation_key` o el `topic` en la CLI, ni tocar `root/store/conversations/` por fuera de `persist_conversation_index` ni `root/store/topics/` por fuera de `persist_topic_index`.
- Don't: alterar el resumen por culpa de la indexacion: ni claves nuevas ni `persisted_paths` mezclada con rutas de indices (ni de `store/conversations/` ni de `store/topics/`); los errores de `persist_conversation_index` o de `persist_topic_index` se tratan como los demas errores de operacion (mensaje generico, codigo `1`).
- Don't: leer, escribir, reparar o borrar `.email-agent/cursors.json` por su cuenta, reimplementar el store de cursor, calcular `since_uid` por cuenta propia (el filtro lo aplica `fetch_imap_messages`), guardar el cursor con bandeja vacia, guardarlo con un valor distinto del maximo `imap_uid` (menor, mayor, o derivado de algo que no sean los records), guardarlo mas de una vez por ejecucion o guardarlo sin un `sync_email_account` exitoso.
- Don't: imprimir `password`, el secreto resuelto o `credential_ref` en stdout, en stderr ni en mensajes de error (los errores son genericos, incluidos los del cursor).
- Don't: abrir sockets ni hablar IMAP fuera de `fetch_imap_messages`, ni usar subprocess, `eval` o `exec`.
- Don't: alterar los subcomandos `search` ni `account` ni su salida ya congelada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_sync.py`. Son oracle independiente: no importan el target ni `src.email`, no abren red real ni usan secretos reales. Verifican la estructura del contrato (frontmatter, presupuestos, 7 secciones, frase de parada), que congela la delegacion en las once firmas dependientes (incluidas las dos del cursor) y la prohibicion de reimplementarlas, y re-derivan los casos congelados con una CLI de referencia propia (store JSON espejo, resolver de credenciales espejo, sesion IMAP simulada, store de cursor espejo en `.email-agent/cursors.json`, persistencia, indice de conversaciones, indice de temas y contactos de referencia) contrastando contra los `frozen-cases`: codigo exacto, stdout de una linea JSON con las 5 claves del resumen, `persisted_paths` en orden y SIN rutas de indices (ni `store/conversations/` ni `store/topics/` ni del cursor), persistencias via `persist_email_okf_at` con rel_path `store/emails/<raw_sha256>.md` seguidas de la indexacion via `persist_conversation_index(root, record, rel_path)` y luego via `persist_topic_index(root, record, rel_path)` en ese orden (con el indice resultante en `store/conversations/<conversation_key>.md` y los nodos de tema en `store/topics/<topic>.md`, ambos ajenos al resumen y con el retorno `int` de `persist_topic_index` descartado), delegacion de contactos a `store_email_contacts(root, contacts)` (conteo de llamadas), host elegido (explicito o default por provider), cursor incremental (carga ANTES del fetch, `since_uid` en la config de fetch, `save_sync_cursor` con el maximo `imap_uid` solo si hubo records y con bandeja vacia sin avanzar, y fallo de cursor como error operativo con codigo `1`), conteo de llamadas (fetch/persist/contactos) y ausencia de secretos en toda la salida.

```frozen-cases
[
  {
    "name": "help_shows_usage",
    "argv": ["--help"],
    "code": 0,
    "stdout_has": ["usage:", "sync ROOT ACCOUNT_ID [HOST]"],
    "stderr": []
  },
  {
    "name": "sync_with_explicit_host",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "personal", "imap.custom.test"],
    "code": 0,
    "expected_host": "imap.custom.test",
    "expected_since_uid": 0,
    "messages": [
      {"raw_sha256": "a1a1a1a1", "subject": "Hola", "from": "Ana Garcia <ana@example.com>", "to": "yo@example.com", "cc": ""},
      {"raw_sha256": "b2b2b2b2", "subject": "Segunda", "from": "Ana Garcia <ana@example.com>", "to": "Carlos <carlos@example.com>", "cc": "Luis <luis@example.com>"}
    ],
    "cursor_saves": [["personal", 2]],
    "persist_paths": ["store/emails/a1a1a1a1.md", "store/emails/b2b2b2b2.md"],
    "contacts": [
      {"email": "ana@example.com", "name": "Ana Garcia"},
      {"email": "yo@example.com", "name": ""},
      {"email": "carlos@example.com", "name": "Carlos"},
      {"email": "luis@example.com", "name": "Luis"}
    ],
    "stdout_json": {"account_id": "personal", "fetched": 2, "persisted": 2, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_default_host_gmail",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "personal"],
    "code": 0,
    "expected_host": "imap.gmail.com",
    "expected_since_uid": 0,
    "messages": [
      {"raw_sha256": "c3c3c3c3", "subject": "Solo", "from": "Dana <dana@example.com>", "to": "yo@example.com", "cc": ""}
    ],
    "cursor_saves": [["personal", 1]],
    "persist_paths": ["store/emails/c3c3c3c3.md"],
    "contacts": [
      {"email": "dana@example.com", "name": "Dana"},
      {"email": "yo@example.com", "name": ""}
    ],
    "stdout_json": {"account_id": "personal", "fetched": 1, "persisted": 1, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_default_host_outlook",
    "store": [
      {"account_id": "work", "provider": "outlook", "email": "work@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "work"],
    "code": 0,
    "expected_host": "outlook.office365.com",
    "expected_since_uid": 0,
    "messages": [
      {"raw_sha256": "d4d4d4d4", "subject": "Estado", "from": "work@example.com", "to": "", "cc": "Eva <eva@example.com>"}
    ],
    "cursor_saves": [["work", 1]],
    "persist_paths": ["store/emails/d4d4d4d4.md"],
    "contacts": [
      {"email": "work@example.com", "name": ""},
      {"email": "eva@example.com", "name": "Eva"}
    ],
    "stdout_json": {"account_id": "work", "fetched": 1, "persisted": 1, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_cursor_advances",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "personal"],
    "code": 0,
    "expected_host": "imap.gmail.com",
    "expected_since_uid": 0,
    "messages": [
      {"raw_sha256": "e5e5e5e5", "subject": "Cursor", "from": "Ana Garcia <ana@example.com>", "to": "yo@example.com", "cc": "", "imap_uid": 41},
      {"raw_sha256": "f6f6f6f6", "subject": "Ultimo", "from": "Ana Garcia <ana@example.com>", "to": "yo@example.com", "cc": "", "imap_uid": 57}
    ],
    "cursor_saves": [["personal", 57]],
    "persist_paths": ["store/emails/e5e5e5e5.md", "store/emails/f6f6f6f6.md"],
    "contacts": [
      {"email": "ana@example.com", "name": "Ana Garcia"},
      {"email": "yo@example.com", "name": ""}
    ],
    "stdout_json": {"account_id": "personal", "fetched": 2, "persisted": 2, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_cursor_resume",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "tree": {".email-agent/cursors.json": "{\"cursors\":{\"personal\": 100}}"},
    "argv": ["sync", "<root>", "personal"],
    "code": 0,
    "expected_host": "imap.gmail.com",
    "expected_since_uid": 100,
    "messages": [
      {"raw_sha256": "a7a7a7a7", "subject": "Viejo", "from": "Ana Garcia <ana@example.com>", "to": "yo@example.com", "cc": "", "imap_uid": 100},
      {"raw_sha256": "b8b8b8b8", "subject": "Nuevo", "from": "Ana Garcia <ana@example.com>", "to": "yo@example.com", "cc": "", "imap_uid": 101}
    ],
    "cursor_saves": [["personal", 101]],
    "persist_paths": ["store/emails/b8b8b8b8.md"],
    "contacts": [
      {"email": "ana@example.com", "name": "Ana Garcia"},
      {"email": "yo@example.com", "name": ""}
    ],
    "stdout_json": {"account_id": "personal", "fetched": 1, "persisted": 1, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_empty_mailbox_keeps_cursor",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "tree": {".email-agent/cursors.json": "{\"cursors\":{\"personal\": 30}}"},
    "argv": ["sync", "<root>", "personal"],
    "code": 0,
    "expected_host": "imap.gmail.com",
    "expected_since_uid": 30,
    "messages": [],
    "cursor_saves": [],
    "persist_paths": [],
    "contacts": [],
    "stdout_json": {"account_id": "personal", "fetched": 0, "persisted": 0, "contacts_updated": true},
    "stderr": [],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_cursor_corrupt",
    "tree": {".email-agent/cursors.json": "{\"cursors\":{\"personal\": \"no-es-int\"}}"},
    "argv": ["sync", "<root>", "personal"],
    "code": 1,
    "fetch_calls": 0,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": []
  },
  {
    "name": "sync_account_missing",
    "store": [],
    "environ": {},
    "argv": ["sync", "<root>", "inexistente"],
    "code": 1,
    "fetch_calls": 0,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": []
  },
  {
    "name": "sync_credential_missing",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://VARIABLE_AUSENTE", "status": "disconnected"}
    ],
    "environ": {},
    "argv": ["sync", "<root>", "personal"],
    "code": 1,
    "fetch_calls": 0,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["env://VARIABLE_AUSENTE", "VARIABLE_AUSENTE", "credential_ref"]
  },
  {
    "name": "sync_unknown_provider_no_host",
    "store": [
      {"account_id": "extra", "provider": "unknown", "email": "x@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "extra"],
    "code": 1,
    "fetch_calls": 0,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_fetch_error",
    "store": [
      {"account_id": "personal", "provider": "gmail", "email": "yo@example.com", "credential_ref": "env://EMAIL_PASSWORD", "status": "disconnected"}
    ],
    "environ": {"EMAIL_PASSWORD": "MARCADOR-SECRETO-123"},
    "argv": ["sync", "<root>", "personal", "imap.falla.test"],
    "fetch_error": true,
    "code": 1,
    "fetch_calls": 1,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": ["env://EMAIL_PASSWORD", "MARCADOR-SECRETO-123", "credential_ref"]
  },
  {
    "name": "sync_corrupt_store",
    "tree": {".email-agent/accounts.json": "{no es json"},
    "argv": ["sync", "<root>", "personal"],
    "code": 1,
    "fetch_calls": 0,
    "persist_paths": [],
    "contacts": [],
    "stdout": [],
    "stderr_has": ["error"],
    "secrets": []
  },
  {
    "name": "sync_no_args",
    "argv": ["sync"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "sync_missing_args",
    "argv": ["sync", "<root>"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  },
  {
    "name": "sync_extra_args",
    "argv": ["sync", "<root>", "personal", "imap.x", "extra"],
    "code": 2,
    "stdout": [],
    "stderr_has": ["usage:"]
  }
]
```

## Constraints

La CLI debe permanecer una capa fina de presentacion sobre `src.email.account_store.load_email_accounts` con la firma `def load_email_accounts(root: str) -> list`, sobre `src.email.credentials.resolve_credential` con la firma `def resolve_credential(credential_ref: str, environ=None) -> str`, sobre `src.email.imap_reader.fetch_imap_messages` con la firma `def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list`, sobre `src.email.sync.sync_email_account` con la firma `def sync_email_account(account: dict, fetch_messages, persist_message, update_contacts=None) -> dict`, sobre `src.email.persist_at.persist_email_okf_at` con la firma `def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`, sobre `src.email.conversation_index.persist_conversation_index` con la firma `def persist_conversation_index(root: str, record: dict, message_path: str) -> str`, sobre `src.email.topic_index.persist_topic_index` con la firma `def persist_topic_index(root: str, record: dict, message_path: str) -> int`, sobre `src.email.contacts.extract_contacts` con la firma `def extract_contacts(record: dict) -> list`, sobre `src.email.contact_store.store_email_contacts` con la firma `def store_email_contacts(root: str, contacts: list) -> int`, sobre `src.email.cursor_store.load_sync_cursor` con la firma `def load_sync_cursor(root: str, account_id: str) -> int` y sobre `src.email.cursor_store.save_sync_cursor` con la firma `def save_sync_cursor(root: str, account_id: str, uid: int) -> str`, todas delegadas y jamas reimplementadas dentro de la CLI; la escritura de persistencia se hace UNICAMENTE via `persist_email_okf_at` con el rel_path `store/emails/<raw_sha256>.md` relativo al root, la de indices de conversacion UNICAMENTE via `persist_conversation_index` (que deja el indice en `root/store/conversations/<conversation_key>.md`, invocada DESPUES de `persist_email_okf_at` con el mismo rel_path como `message_path`, sin alterar el resumen ni `persisted_paths`), la de indices de temas UNICAMENTE via `persist_topic_index` (que deja los nodos en `root/store/topics/<topic>.md`, invocada DESPUES de `persist_conversation_index` con el mismo rel_path como `message_path`, con su retorno `int` descartado y sin alterar el resumen ni `persisted_paths`) y la de contactos UNICAMENTE via `store_email_contacts`; la lectura del cursor incremental se hace UNICAMENTE via `load_sync_cursor(root, account_id)` ANTES del fetch y su valor entra como `since_uid` int en la config de fetch, y su escritura UNICAMENTE via `save_sync_cursor(root, account_id, max_uid)` UNA vez por ejecucion, DESPUES de un `sync_email_account` exitoso y ANTES de imprimir el resumen, SOLO si hubo records y con el MAXIMO `imap_uid` (int) de ellos, dejando la bandeja vacia el cursor intacto (sin escribir ni avanzar); y los subcomandos `search` y `account` deben quedar intactos segun los contratos `cli_search` y `cli_accounts`. PARAR y reportar si el modulo o la funcion de cualquiera de esas once dependencias no existen con esa firma, si hay que reimplementar la lectura de cuentas, la resolucion de la credencial, el fetch IMAP, la orquestacion, la persistencia OKF, la indexacion de conversaciones, la indexacion de temas, la extraccion y fusion de contactos o el store de cursor dentro de la CLI, si el cursor no se pudiera cargar ANTES del fetch via `load_sync_cursor` o `since_uid` no pudiera entrar en la config de fetch con el valor cargado, si el callback `fetch` tuviera que devolver algo distinto de la lista verbatim de records o un record no garantizara `imap_uid` int, si el cursor no se pudiera guardar UNA sola vez tras un `sync_email_account` exitoso con el maximo `imap_uid`, si el cursor tuviera que avanzarse o escribirse con bandeja vacia, si un fallo de carga o de guardado del cursor no se pudiera traducir a un mensaje generico en stderr SIN secretos con codigo `1`, si el guardado del cursor alterara el resumen, `persisted_paths` o las 5 claves del resumen, si la CLI tuviera que leer o escribir `.email-agent/cursors.json` por su cuenta, si el orden del callback `persist` (primero `persist_email_okf_at`, despues `persist_conversation_index`, luego `persist_topic_index`) no se pudiera respetar o el callback tuviera que devolver algo distinto de la ruta del mensaje, si el indice de conversaciones tuviera que quedar fuera de `root/store/conversations/<conversation_key>.md` o los nodos de tema fuera de `root/store/topics/<topic>.md`, o si cualquiera de las dos indexaciones alterara el summary, `persisted_paths` o las 5 claves del resumen, si un error de `persist_conversation_index` o de `persist_topic_index` no se pudiera traducir a un mensaje generico en stderr con codigo `1`, si el subcomando `search` o `account` ya congelados tuvieran que cambiar de semantica, si no se pueden respetar los codigos `0`/`1`/`2` ni la separacion stdout/stderr, si `password`, el secreto resuelto o `credential_ref` tuvieran que aparecer en stdout, en stderr o en un mensaje de error, si el secreto tuviera que guardarse, loguearse o persistirse en lugar de vivir solo en memoria, si se necesitara subprocess, `eval` o `exec`, o si la sesion IMAP tuviera que abrirse fuera de `fetch_imap_messages` o en un modo distinto de solo lectura.