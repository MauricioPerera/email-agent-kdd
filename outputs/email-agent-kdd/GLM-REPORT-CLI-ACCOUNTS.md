# GLM-REPORT-CLI-ACCOUNTS

## Resumen

Se integro el subcomando `account` (`add` y `list`) en `cli_main` de
`src/email/cli.py` conforme al contrato `cli-accounts.md`, preservando intacta
la semantica congelada de `search ROOT QUERY`. `account add` delega la
creacion en `create_email_account` y la persistencia en `save_email_account`,
imprimiendo unicamente `account saved: ACCOUNT_ID`. `account list` delega la
lectura en `load_email_accounts` e imprime una linea JSON por cuenta
(`json.dumps(..., sort_keys=True)`) con solo `account_id`, `provider`, `email`
y `status`; raiz o archivo ausente produce stdout vacio con retorno 0. Los
errores de argumentos retornan 2 con usage amigable en stderr; los de
validacion/almacenamiento (`ValueError`/`RuntimeError`) retornan 1 con mensaje
generico sin `credential_ref`, secretos ni traceback. Nota: se usa parseo
manual equivalente en lugar de `argparse` (el propio contrato lo admite en
"## Do / Don't"); los modulos usados son solo `json` y `sys` mas las funciones
existentes. Ningun archivo fuera de `src/email/cli.py` fue modificado; el
contrato y las pruebas congeladas permanecen intactos.

## Archivos tocados

- `src/email/cli.py` (reescritura de la capa de presentacion; `search`
  conserva el mismo parseo, codigos 0/1/2 y salida una-ruta-por-linea).

## Verificacion

1. `python -m pytest -q outputs/email-agent-kdd/tests/frozen_cli_accounts.py`
   → `14 passed`.
2. `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"`
   → `127 passed`.
3. Smoke tests reales con `tempfile.TemporaryDirectory()` (sin credenciales
   reales, referencias opacas de mentira tipo `vault://SECRETO-X`):
   - `account add`: stdout exacto `account saved: personal`, retorno 0,
     `accounts.json` creado con `provider "gmail"`, `email
     "yo@example.com"`, `status "disconnected"` y `credential_ref` verbatim
     solo en el store.
   - `account list` (2 cuentas): dos lineas JSON ordenadas por `account_id`,
     sin `credential_ref` ni `vault://` en stdout/stderr, retorno 0.
   - `account list` en raiz inexistente: stdout vacio, stderr vacio, retorno 0.
   - `search ROOT QUERY` sobre arbol temporal: `docs/guia.md` en stdout,
     retorno 0 (semantica intacta).
   - Errores de argumentos (`[]`, `["bogus"]`, `["account"]`,
     `["account","frobnicate",root]`, `["account","list"]`, arity corto de
     `account add` y `search`): retorno 2, stdout vacio, `usage:` en stderr,
     sin traceback.
   - `--help` / `-h`: retorno 0, usage en stdout con `account add ...` y
     `search ROOT QUERY`, stderr vacio.
   - Errores de validacion (provider en blanco) y almacenamiento
     (`accounts.json` corrupto en `add` y en `list`): retorno 1, stdout vacio,
     mensaje generico con `error` en stderr, sin `credential_ref`, sin
     secretos, sin traceback.
   Primera pasada del smoke marco un fallo por un bug del propio script de
   humo (expectativa que omitia una cuenta persistida en el paso anterior);
   corregida la expectativa, `SMOKE OK`.

## Estado

LISTO. Los 14 tests del oráculo congelado y los 127 tests congelados del
proyecto pasan; los smoke tests de `account add`, `account list` (incluida
raiz ausente), errores de argumentos (2), errores de almacenamiento/validacion
(1) y `search` intacto pasan sin filtrar `credential_ref` ni secretos.