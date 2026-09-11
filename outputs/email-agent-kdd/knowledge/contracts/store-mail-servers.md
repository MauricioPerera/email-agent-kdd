---
task: store_mail_server_config
intent: guardar y leer la configuracion publica de servidores IMAP/SMTP por cuenta en un store JSON local, jamas secretos
target: src/email/mail_server_store.py
signature: "def store_mail_server_config(root: str, account_id: str, config: dict) -> str"
budget:
  cyclomatic_max: 16
  nesting_max: 3
  lines_max: 60
  params_max: 3
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_store_mail_servers.py -q"
tests: tests/frozen_store_mail_servers.py
deps_allowed: [json, os, pathlib]
forbids: [eval, exec, subprocess, network_access, socket, smtplib, imaplib, urllib, requests, pickle, getpass, keyring, logging, print, environ]
---

## Intent

Persistir localmente la configuracion PUBLICA de servidores de correo que produce `discover_mail_servers` (o el formulario avanzado) y releerla: `store_mail_server_config(root, account_id, config)` guarda bajo `<root>/.email-agent/mail-servers.json` la entrada de esa cuenta con EXACTAMENTE `imap_host`, `imap_port`, `smtp_host`, `smtp_port`, y devuelve la ruta absoluta del archivo escrito; `load_mail_server_config(root, account_id)` devuelve el registro de esa cuenta o `None` si aun no existe. El archivo SOLO contiene configuracion publica de servidores: JAMAS se acepta ni se almacena `password`, `credential_ref`, `secret`, `token` ni ninguna clave extra. La escritura es atomica y determinista; el reemplazo por `account_id` es idempotente. Ninguna funcion abre red, imprime ni ejecuta procesos, y los mensajes de error son genericos sin filtrar el contenido del store.

## Interface

`def store_mail_server_config(root: str, account_id: str, config: dict) -> str`
`def load_mail_server_config(root: str, account_id: str) -> dict`

Ambas funciones viven en el mismo target; al implementar, anclar `target_line` a la linea de `store_mail_server_config` y documentar la linea de `load_mail_server_config`.

- `root`: directorio raiz del store (`str` no vacio tras `strip`). Bajo el se usa la ruta unica `<root>/.email-agent/mail-servers.json`; ninguna funcion escribe fuera de ella.
- `account_id`: `str` no vacio que case EXACTAMENTE con `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (ASCII, sin espacios, sin `/`, sin `\`, sin Unicode). Se usa verbatim como clave del mapa `servers`.
- `config`: registro EXACTO de cuatro claves: `imap_host`, `imap_port`, `smtp_host`, `smtp_port`. Ninguna otra clave (por ejemplo `password`, `credential_ref`, `secret`, `token`, `user`, `tls`) se acepta; falta o sobra una clave -> `ValueError`.
- `imap_host` / `smtp_host`: `str` ASCII en minusculas que case EXACTAMENTE con `^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$`, longitud <= 253, sin `..` (etiquetas vacias) y sin punto inicial/final (el ancla de la regex ya lo prohibe). Sin mayusculas, sin espacios, sin esquema (`imap://`), sin ruta.
- `imap_port` / `smtp_port`: `int` (se rechaza `bool`, `float`, `str` y `None`) en 1..65535.
- Los valores se guardan VERBATIM: la validacion y la normalizacion (minusculas, dominio) ya las hizo `discover_mail_servers` o el formulario; aqui no se re-normaliza nada.
- `store_mail_server_config` devuelve: la ruta absoluta del archivo `mail-servers.json` escrito (`str`).
- `load_mail_server_config` devuelve: `dict` con EXACTAMENTE las cuatro claves del registro de esa cuenta; `None` si el archivo no existe o la cuenta no esta en el store.
- Lanza: `ValueError` generico si `root`, `account_id` o `config` no cumplen el esquema (ambas funciones validan antes de tocar disco). `load_mail_server_config` lanza `RuntimeError` generico si el archivo existe pero esta corrupto (JSON ilegible) o fuera de esquema (top-level distinto de un objeto con la unica clave `servers`, o cualquier entrada que no cumpla el registro). Los mensajes son genericos: jamas incluyen el contenido de las entradas ni los hosts.
- Escritura (regla exacta): el archivo es JSON UTF-8 determinista, un objeto con la unica clave `servers` que mapea `account_id` -> registro de cuatro claves, serializado con claves ordenadas y `ensure_ascii=False`, terminado en salto de linea. La escritura es atomica: primero un archivo temporal en el MISMO directorio y luego `os.replace`; un fallo entre ambos pasos no deja un `mail-servers.json` parcial ni truncado. Si `account_id` ya existe su entrada se REEMPLAZA (gana la ultima, sin duplicados); las demas cuentas se conservan intactas. Si el archivo existe pero esta corrupto o fuera de esquema, store PARAR con `RuntimeError` generico en lugar de sobreescribir datos que no entiende.

### Integracion con discovery y el formulario

- `discover_mail_servers` devuelve exactamente el registro de cuatro claves que esta funcion persiste; el formulario avanzado puede construir el mismo dict a mano. En ambos casos lo guardado es SOLO configuracion publica de servidores: hosts y puertos, datos que el DNS ya publica.
- El secreto de la cuenta sigue su propio camino (`wincred://<label>` en Credential Manager) y vive en `accounts.json` como `credential_ref`: este store JAMAS lo recibe, lo acepta ni lo almacena.
- Tras `load_mail_server_config`, los hosts/puertos alimentan la conexion de la cuenta (`sync`/`send`); la lectura no muta el store.

## Invariants

- El store vive siempre en `<root>/.email-agent/mail-servers.json`; ninguna funcion escribe fuera de esa ruta y jamas se deriva una ruta de datos del usuario.
- En disco solo se guardan las cuatro claves del registro por cuenta: jamas un secreto, ni `password`, ni `credential_ref`, ni claves extra, ni `bytes`.
- La escritura es atomica (temporal en el mismo directorio + `os.replace`) y el JSON en disco es determinista: mismo contenido -> mismos bytes exactos, sin reloj ni azar.
- Reemplazo por `account_id` idempotente: tras guardar dos veces la misma cuenta el store contiene exactamente una entrada y gana la ultima; las otras cuentas no se tocan.
- `load_mail_server_config` devuelve un dict con EXACTAMENTE las cuatro claves: nunca claves extra ni parciales; archivo o cuenta ausentes => `None`.
- Archivo presente pero corrupto o fuera de esquema => `RuntimeError` generico; los mensajes de error (de `ValueError` y de `RuntimeError`) jamas contienen hosts, contenido del store ni nombres de cuenta.
- No hay red, impresion ni procesos: no se conecta a servidores, no abre sockets y no importa `smtplib`, `imaplib`, `socket`, `urllib` ni `requests`; no usa `subprocess` ni `print`.
- Las funciones no mutan los argumentos de entrada.

## Examples

Ejemplo frozen: guardar la configuracion de `discover_mail_servers` para la cuenta `personal` sobre un store vacio deja exactamente estos bytes en `<root>/.email-agent/mail-servers.json`, y la funcion devuelve la ruta absoluta de ese archivo.

```frozen-inputs
{"account_id": "personal", "config": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}}
```

```frozen-example
{"servers": {"personal": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}}}
```

- Entrada del ejemplo: el par `(account_id, config)` sobre un store vacio (directorio temporal propio); el contenido del archivo es EXACTAMENTE el bloque `frozen-example` serializado con claves ordenadas, `ensure_ascii=False` y salto de linea final.
- Reemplazo: guardar de nuevo `personal` con `{"imap_host": "outlook.office365.com", "imap_port": 993, "smtp_host": "smtp.office365.com", "smtp_port": 587}` deja UNA entrada y gana la nueva; una cuenta `work` guardada antes se conserva igual.
- `load_mail_server_config` sobre un store vacio o sin la cuenta devuelve `None`; sobre el ejemplo devuelve el registro exacto de cuatro claves.
- `store_mail_server_config(root, "gmail app", config)`, `store_mail_server_config(root, "../escape", config)`, `store_mail_server_config(root, "", config)` y `store_mail_server_config(root, None, config)` lanzan `ValueError` y NO crean ni tocan ningun archivo.
- `config` con una clave de mas (`password`, `credential_ref`, `token`), con una clave faltante, con host `IMAP.GMAIL.COM`, `"imap gmail.com"`, `".gmail.com"`, `"a..b.com"` o puerto `0`, `65536`, `True`, `"993"`, `993.0` lanzan `ValueError` generico.
- Archivo corrupto (`b"{no json"`), top-level lista, o un registro con clave extra `password` => `load_mail_server_config` lanza `RuntimeError` generico sin revelar el contenido.

## Do / Don't

- Do: validar `root`, `account_id` y el registro completo (cuatro claves exactas, hosts ASCII minusculas, puertos `int` 1..65535 sin `bool`) ANTES de tocar disco.
- Do: fusionar con el store existente, reemplazar solo la entrada de `account_id`, serializar con claves ordenadas y `ensure_ascii=False` con salto final, y escribir con temporal en el mismo directorio + `os.replace`.
- Do: devolver la ruta absoluta al guardar; devolver el registro de cuatro claves, o `None` si el archivo o la cuenta no existen.
- Do: traducir JSON corrupto o esquema invalido a `RuntimeError` generico, en ambas funciones, sin reescribir el archivo.
- Don't: aceptar ni persistir `password`, `credential_ref`, `secret`, `token` ni ninguna clave fuera de las cuatro; tampoco hosts en mayusculas o con separadores, puertos no `int` (incluido `bool`) fuera de 1..65535, ni `account_id` con espacios, separadores o Unicode.
- Don't: escribir fuera de `<root>/.email-agent/mail-servers.json`, dejar archivos temporales residuales, imprimir, loguear, abrir red o usar `subprocess`.
- Don't: incluir datos del store en los mensajes de error, mutar los argumentos de entrada ni depender de librerias de terceros.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_store_mail_servers.py`. Son oracle independiente: NO importan `src.email` ni el target y JAMAS tocan un store real; usan directorios temporales propios. Verifican la estructura del contrato (frontmatter con presupuestos y `params_max: 3`, 7 secciones, ambas firmas, regla `PARAR y reportar si`, dependencias `json`/`os`/`pathlib`, prohibicion de `subprocess`/`smtplib`/`socket`/`print`, ruta `.email-agent/mail-servers.json`, clave `servers`, atomicidad con `os.replace`, y prohibicion de `password`/`credential_ref`) y ejercitan un modelo de referencia reimplementado en el propio test con las reglas documentadas: ejemplo frozen exacto en bytes, determinismo (mismos bytes en stores distintos), reemplazo idempotente por `account_id` conservando otras cuentas, carga ausente => `None`, rechazo con `ValueError` de roots/account_ids/configs invalidos (incluidos traversal y secretos), rechazo con `RuntimeError` generico de stores corruptos o fuera de esquema, ausencia de secretos en disco y en errores, ruta confinada a `root`, y ausencia de canales de escape (red, print, subprocess) en el modelo.

## Constraints

Presupuestos por funcion: ciclomatica <= 16, anidamiento <= 3, lineas <= 60, parametros <= 3. Solo dependencias de `deps_allowed` (`json`, `os`, `pathlib`; stdlib, sin importar nada de `src.email`). Las funciones jamas abren red, imprimen, loguean ni ejecutan procesos; solo escriben el archivo `<root>/.email-agent/mail-servers.json` (via temporal en el mismo directorio + `os.replace`); jamas aceptan ni almacenan secretos, `password`, `credential_ref` ni claves fuera de las cuatro del registro; la carga ausente devuelve `None` y la corrupta/invalida `RuntimeError` generico sin filtrar datos. PARAR y reportar si el esquema de cuatro claves no cubre un dato real de servidor (por ejemplo TLS explicito), si se necesitara persistir secretos o referencias de credencial en este store, si la escritura atomica con `os.replace` no pudiera garantizarse en la plataforma, si se necesitara escribir fuera de `<root>/.email-agent/` o leer de otro archivo, si los mensajes de error no pudieran ser genericos, si `load` necesitara devolver parcial en lugar de `None`/`RuntimeError`, o si se necesitara red, `subprocess` o dependencias fuera de `json`, `os` y `pathlib`.