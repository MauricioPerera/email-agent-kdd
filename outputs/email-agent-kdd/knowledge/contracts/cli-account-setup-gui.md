---
task: cli_account_setup_gui
intent: agregar el subcomando account setup-gui ROOT con un formulario local para usuarios no tecnicos que guarda el secreto solo en el almacenamiento seguro nativo de la plataforma
target: src/email/gui_setup.py
signature: "def run_account_setup_gui(root: str) -> int"
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 120
  params_max: 3
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_cli_account_setup_gui.py -q"
tests: tests/frozen_cli_account_setup_gui.py
deps_allowed: [tkinter, src.email.provision_account, src.email.discover_mail_servers, src.email.mail_server_store]
forbids: [eval, exec, subprocess, cmdkey, network_access, socket, urllib, requests, smtplib, logging, print, open, getpass, input, os.environ, keyring]
---

## Intent

Exponer en la CLI local de correo el subcomando `account setup-gui ROOT`: al ejecutarlo, `run_account_setup_gui(root)` abre UN formulario tkinter local (ventana de escritorio estandar, sin navegador, sin servidor HTTP y sin procesos externos) para usuarios no tecnicos con SOLO dos campos visibles, `email` y `password` (Entry con `show="*"`): el usuario JAMAS introduce `account_id` ni elige proveedor. Al pulsar Guardar se llama UNA sola vez `discover_mail_servers(email)` SIN la contrasena; si descubre ambos servidores se muestra una confirmacion publica y se continua; si no, la MISMA ventana revela una seccion avanzada amigable para introducir servidor y puerto de entrada (IMAP) y de salida (SMTP), validados con las reglas del almacen de servidores, sin pedir terminos tecnicos adicionales. Con los servidores resueltos se entrega el secreto DIRECTAMENTE en memoria a `provision_email_account(root, account_id, "custom", email, label, secret)`, que elige el almacenamiento seguro NATIVO por plataforma (`win32` -> Credential Manager, `darwin` -> Keychain, `linux` -> Secret Service) y persiste en `accounts.json` el `credential_ref` publico de ESA plataforma (`wincred://<label>`, `keychain://<label>` o `secretservice://<label>`); despues `store_mail_server_config(root, account_id, config)` persiste los hosts en `.email-agent/mail-servers.json`. El formulario JAMAS imprime, registra, devuelve ni envia el secreto al agente, y solo muestra mensajes genericos. Cancelar no escribe nada; el exito muestra una confirmacion publica sin `credential_ref` ni secreto; todo fallo limpia el password y muestra un mensaje generico; si el almacen nativo de la plataforma no esta disponible (incluidos macOS/Linux sin su backend) muestra una PARADA clara que nombra el OS y JAMAS ofrece un fallback inseguro.

## Interface

`def run_account_setup_gui(root: str) -> int` (en `src/email/gui_setup.py`).

Rama CLI (en `src/email/cli.py`, misma funcion `cli_main` ya implementada; se agrega la rama `account setup-gui`, no se reemplaza nada):

- `python -m src.email account setup-gui ROOT` (exactamente un argumento tras el subcomando): abre el formulario con esa raiz y retorna el codigo que devuelve `run_account_setup_gui(root)`. La rama NO imprime nada en stdout ni en stderr durante el flujo del formulario: todos los mensajes del flujo van a la ventana.
- `account setup-gui` sin ROOT, o con mas de un argumento: mensaje amigable + usage en stderr, retorna `2` (mismo criterio que los demas subcomandos de `account`).
- `--help`/usage: se agrega la linea `account setup-gui ROOT` a la ayuda existente; los subcomandos ya existentes (`search`, `account add`, `account list`, `account setup`, `query`, `sync`, `draft` y `send`) quedan intactos con su semantica ya congelada.

Formulario (una unica ventana tkinter, campos en este orden de arriba hacia abajo):

1. `email`: Entry de texto; respuesta recortada con `strip()` al usarla.
2. `password`: Entry con `show="*"`; el valor se lee VERBATIM (sin `strip` ni transformacion alguna) y existe solo en memoria.
3. Estado: una etiqueta de mensajes genericos no terminales.
4. Botones: `Guardar` y `Cancelar`.
5. Seccion avanzada OCULTA al inicio (LabelFrame `Configuracion avanzada del servidor de correo`) con solo cuatro campos amigables: `Servidor de entrada (IMAP)` y `Puerto de entrada`, `Servidor de salida (SMTP)` y `Puerto de salida`. Se revela SOLO dentro de la misma ventana cuando el discovery no confirma ambos servidores; jamas se piden terminos tecnicos adicionales (sin SSL, sin tipo de autenticacion, sin account_id, sin proveedor).

`account_id` derivado (JAMAS pedido al usuario): dada la respuesta de `email` recortada, se toma `local + "-" + domain` en minusculas, se reemplaza cada secuencia de caracteres fuera de `[a-z0-9._-]` por `-`, se colapsan guiones repetidos, se recortan `-._` de los bordes, se trunca a 57 caracteres, se vuelven a recortar los bordes y, si queda vacio, se usa `cuenta`. Con 57 el label derivado `"email-" + account_id` cabe siempre en el limite de 64 de la etiqueta de credencial. El label derivado se VALIDA contra la regex `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` antes de cualquier efecto (defensivo); si no casa, mensaje generico sin tocar el almacenamiento. El proveedor del alta es SIEMPRE la etiqueta publica documentada `custom` (el selector de proveedor desaparece; `create_email_account` la normaliza sin restringirla).

Pipeline EXACTO al pulsar `Guardar` (en este orden; el password solo se lee dentro de este pipeline, JAMAS antes):

1. Leer `email` (recortado) y `password` (verbatim). Si alguno queda vacio: mensaje generico NO terminal en la ventana, sin discovery ni provision; la ventana permanece abierta para reintentar o cancelar.
2. Si no hay servidores resueltos aun y el discovery no se intento en esta sesion: UNA sola llamada `discover_mail_servers(email)` pasando SOLO el email (sin contrasena, sin resolver propio; la unica red es la DNS publica delegada en el contrato `discover-mail-servers`).
   - Exito: fijar los cuatro valores (`imap_host`, `imap_port`, `smtp_host`, `smtp_port`), mostrar UNA confirmacion publica en la ventana y CONTINUAR al paso 4.
   - `ValueError` (no confirmados): revelar la seccion avanzada en la misma ventana, mostrar un mensaje generico de guia NO terminal, NO provisionar, NO escribir nada; la ventana permanece abierta y el password permanece UNICAMENTE en el widget. El discovery NO se reintenta en esta sesion: tras este punto los servidores solo provienen de la seccion avanzada.
   - Cualquier otra excepcion: mensaje generico, limpiar password, cerrar la ventana y retornar `1`.
3. Si el discovery fallo (seccion avanzada activa) y los servidores siguen sin resolverse: leer los cuatro campos avanzados (hosts recortados y en minusculas; puertos recortados y convertidos a `int`), y validarlos con las REGLAS DEL ALMACEN `store_mail_server_config` (host: no vacio, <= 253, sin `..`, contra `^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$`; puerto: int entre 1 y 65535). Con algun campo vacio, puerto invalido u host invalido: mensaje generico NO terminal, sin provision y la ventana permanece abierta. Solo con datos completos y validos se fijan los servidores resueltos.
4. Derivar `account_id` y `label = "email-" + account_id`; validar el label contra la regex (defensivo). Si no casa: mensaje generico terminal, limpiar password, cerrar, retornar `1`.
5. Llamar UNA sola vez `provision_email_account(root, account_id, "custom", email, label, password)` pasando el secreto directo desde el widget, solo en memoria (sin copiarlo a atributos, logs, archivos ni variables de entorno). provision elige el almacen nativo por plataforma: `wincred` en Windows, `keychain` en macOS y `secretservice` en Linux.
   - `RuntimeError` de provision (PARADA del almacen nativo: Credential Manager, Keychain o Secret Service indisponible): PARADA clara que nombre el almacenamiento seguro del OS (Windows/macOS/Linux) y que indique que NO existe alternativa segura; JAMAS ofrecer fallback (ni variable de entorno, ni archivo, ni texto en claro); limpiar password, cerrar, retornar `1`. En este caso NO se llama a `store_mail_server_config`.
   - `ValueError` u otra excepcion: mensaje generico sin detalles de la excepcion, limpiar password, cerrar, retornar `1`.
6. Llamar UNA sola vez `store_mail_server_config(root, account_id, config)` con el registro EXACTO de cuatro claves resuelto (discovery o manual). Fallo: mensaje generico, limpiar password, cerrar, retornar `1`.
7. Exito: mostrar en la ventana UNA confirmacion publica tipo `cuenta guardada: <account_id>` (JAMAS `credential_ref`, JAMAS `wincred://...`, JAMAS el secreto ni el label), limpiar el campo password y retornar `0`.

`Cancelar` o cerrar la ventana: cerrar sin llamar a discovery (si no se ejecuto), sin provision, sin `store_mail_server_config`, sin escrituras en disco y sin mensajes; limpiar el password; retornar `1`.

Codigos de salida: `0` solo tras guardado exitoso con su confirmacion en la ventana; `1` para cancelacion, validacion invalida, discovery con excepcion no prevista, fallo de provision, fallo del almacen de servidores o PARADA no-Windows; `2` solo para errores de argumentos de la CLI (usage en stderr).

## Invariants

- El secreto vive UNICAMENTE en la memoria del proceso del formulario: JAMAS se imprime (ni consola ni ventana), loguea, escribe a disco, retorna ni envia al agente (ni en prompts, ni en historial, ni en logs).
- El password JAMAS se usa antes de pulsar Guardar: el discovery y toda la validacion de servidores operan SOLO con el `email`; el widget password no se lee fuera del pipeline de Guardar. Mientras la ventana permanece abierta en estados intermedios (seccion avanzada abierta, datos incompletos) el valor vive solo en el widget; el password se limpia ANTES de cada mensaje terminal y en TODO cierre (exito, fallo, cancelacion).
- El usuario JAMAS introduce `account_id` ni elige proveedor: el id se deriva internamente y de forma DETERMINISTA desde el correo, y el proveedor del alta es siempre la etiqueta publica `custom`.
- La referencia publica del almacen nativo (`wincred://<label>` en Windows, `keychain://<label>` en macOS, `secretservice://<label>` en Linux) va UNICAMENTE en `accounts.json` (via `save_email_account` dentro de provision); los hosts y puertos van UNICAMENTE en `.email-agent/mail-servers.json` (via `store_mail_server_config`); JAMAS un host en `accounts.json` ni el secreto en `mail-servers.json`.
- Orden congelado al guardar: `discover_mail_servers(email)` (o la seccion avanzada) ANTES de `provision_email_account`, y provision ANTES de `store_mail_server_config`. Si el discovery fallo sin datos avanzados completos, NO hay provision ni escritura alguna. Si falla la provision NO se llama al almacen de servidores.
- Prohibiciones absolutas del target: JAMAS `input()`, JAMAS `getpass`, JAMAS variables de entorno (`os.environ`), JAMAS guardar el secreto en archivos, JAMAS red directa (socket/urllib/requests/smtplib: la unica red es la DNS publica delegada en `discover_mail_servers`), JAMAS `subprocess`, JAMAS navegador, JAMAS servidor HTTP; la UI es tkinter estandar local y nada mas.
- El campo password usa SIEMPRE `show="*"`: el valor jamas se muestra en claro en la ventana.
- Los mensajes de la ventana son GENERICOS: sin detalles de excepciones, sin tracebacks, sin `credential_ref`, sin `wincred://`, sin el secreto, sin el label de credencial, sin nombres de variables.
- El secreto se entrega a provision UNA sola vez, directo desde el widget, verbatim (sin `strip`, sin transformacion); el formulario jamas lo copia a estructuras persistentes ni a atributos de larga vida.
- Cancelacion o cierre de ventana: CERO llamadas a provision, CERO escrituras en disco; si el store no existia, no se crea.
- Con exito la confirmacion es publica (solo `account_id` y estado), sin datos de credenciales; sin exito no hay confirmacion.
- En cualquier plataforma, si el almacen nativo no esta disponible (sin Credential Manager, sin Keychain, sin Secret Service): PARAR claro en la ventana, nombrando el OS, y JAMAS un fallback inseguro (ni env, ni archivo plano, ni texto en claro, ni keyring de terceros).
- La CLI conserva intactos todos los subcomandos ya congelados (mismos parseos, codigos y mensajes): la unica adicion es `account setup-gui` y su linea en el usage.
- Sin procesos, sin `eval`/`exec`; las unicas escrituras en disco son las que hacen `provision_email_account` (via `save_email_account`) y `store_mail_server_config` dentro del root indicado; el formulario no escribe nada por su cuenta.

## Examples

```frozen-inputs
{
  "root": "<temp-oracle>",
  "email": "Ana@Example.COM",
  "password": "app-pass-fake-123",
  "discovered": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}
}
```

- Ejemplo frozen: con los valores del bloque `frozen-inputs`, pulsar Guardar produce EXACTAMENTE UNA llamada `discover_mail_servers("Ana@Example.COM")` (sin contrasena, sin resolver), que devuelve el dict descubierto; UNA confirmacion publica en la ventana; UNA llamada `provision_email_account("<temp-oracle>", "ana-example.com", "custom", "Ana@Example.COM", "email-ana-example.com", "app-pass-fake-123")` (email SOLO recortado y sin cambiar mayusculas/minusculas: la normalizacion ocurre DENTRO de provision via `create_email_account`; password verbatim); UNA llamada `store_mail_server_config("<temp-oracle>", "ana-example.com", {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587})`; una confirmacion publica `cuenta guardada: ana-example.com`; el campo password limpio; codigo `0`; en `accounts.json` la ref de la plataforma (`wincred://email-ana-example.com` en Windows, `keychain://...` en macOS, `secretservice://...` en Linux) JAMAS el secreto; en `mail-servers.json` solo los hosts.
- Discovery lanzando `ValueError`: se revela la seccion avanzada en la MISMA ventana con un mensaje generico de guia; cero llamadas a provision y a `store_mail_server_config`; la ventana permanece abierta. Con los campos avanzados `imap.midominio.test/1993` y `smtp.midominio.com/1587` y Guardar de nuevo: UNA llamada a provision con el mismo id derivado y UNA a `store_mail_server_config` con el dict manual, confirmacion publica y codigo `0`.
- Campos avanzados incompletos (uno vacio), puerto `0`, `70000` o `abc`, o host invalido (con espacio, con `..`, vacio): mensaje generico NO terminal, cero llamadas a provision y al almacen, la ventana permanece abierta.
- Discovery lanzando una excepcion no prevista: mensaje generico terminal, password limpio, codigo `1`.
- Provision lanzando `ValueError`: mensaje generico en la ventana sin detalles, password limpio, codigo `1`.
- Provision lanzando `RuntimeError` de PARADA (almacen nativo indisponible en cualquier OS): PARADA clara en la ventana que nombra el almacen del OS y sin ofrecer alternativa alguna, password limpio, codigo `1`, y `store_mail_server_config` NO se llama.
- `store_mail_server_config` lanzando excepcion tras un provision exitoso: mensaje generico terminal, password limpio, codigo `1`.
- Pulsar `Cancelar` (o cerrar la ventana) en cualquier momento: cero llamadas, cero escrituras, codigo `1`.
- `python -m src.email account setup-gui` (sin ROOT) y `python -m src.email account setup-gui ROOT extra`: mensaje + usage en stderr, codigo `2`, el formulario no llega a abrirse.
- `python -m src.email --help` sigue listando los subcomandos ya congelados y agrega `account setup-gui ROOT`.

## Do / Don't

- Do: construir la ventana con tkinter estandar (solo `email` y `password` con `show="*"`, seccion avanzada oculta, botones Guardar/Cancelar) y leer el secreto directo del widget solo en memoria, solo dentro del pipeline de Guardar.
- Do: derivar `account_id` de forma determinista desde el correo con la regla congelada (57 caracteres maximo) y validar el label `"email-" + account_id` contra su regex antes de provision.
- Do: llamar `discover_mail_servers(email)` UNA sola vez por sesion de la ventana, SIN contrasena; con `ValueError` revelar la seccion avanzada en la misma ventana y continuar solo con los cuatro campos completos y validos segun las reglas del almacen.
- Do: delegar TODO el efecto en orden: provision (credencial + `accounts.json`) y despues `store_mail_server_config` (hosts en `mail-servers.json`); el formulario no persiste nada por su cuenta.
- Do: limpiar el campo password en todo cierre y antes de todo mensaje terminal, mostrar mensajes genericos y retornar `0`/`1`/`2` segun el criterio congelado.
- Do: mantener intactos los subcomandos ya congelados y agregar solo `setup-gui` bajo `account` con su linea de usage.
- Don't: pedir al usuario `account_id`, proveedor u otro termino tecnico fuera de los cuatro campos avanzados (servidor y puerto de entrada/salida).
- Don't: usar el password para el discovery, ni `input()`, `getpass`, variables de entorno, archivos para el secreto, red directa, navegador, servidor, `subprocess`, `eval` ni `exec`.
- Don't: imprimir el secreto, `credential_ref`, `wincred://` o detalles de excepciones (ni en la ventana, ni en consola, ni en logs); los mensajes son genericos.
- Don't: ofrecer fallback inseguro cuando el almacen nativo (Credential Manager, Keychain o Secret Service) no este disponible; PARAR con un mensaje claro que nombre el OS y sin alternativas.
- Don't: hacer `strip` ni transformar el password; tampoco retener el secreto en atributos, caches o estructuras de larga vida.
- Don't: provisionar con discovery fallido y datos avanzados incompletos, ni llamar a `store_mail_server_config` si la provision fallo.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_cli_account_setup_gui.py`. Son oracle independiente: NO importan `src.email`, ni `tkinter`, ni abren ventanas reales, ni hacen DNS, ni usan Credential Manager ni secretos reales; verifican la estructura del contrato (frontmatter con target `src/email/gui_setup.py`, firma `run_account_setup_gui(root: str) -> int`, `deps_allowed` con `tkinter`, `src.email.provision_account`, `src.email.discover_mail_servers` y `src.email.mail_server_store`, `forbids` con `input`/`getpass`/`os.environ`/`print`/`open`/socket/red/`subprocess`, 7 secciones, regla `PARAR y reportar si`) y ejercitan un modelo de referencia reimplementado en el propio test con las reglas documentadas sobre una ventana FALSA en memoria, un discovery FALSO, una provision FALSA y un almacen de servidores FALSO: derivacion determinista del account_id desde el correo (incluida la truncacion a 57), flujo exitoso por discovery con UNA llamada a provision (id derivado, provider `custom`, email solo recortado, secreto verbatim) y UNA a `store_mail_server_config` con el dict de cuatro claves, flujo exitoso por seccion avanzada tras un discovery `ValueError` (sin provision hasta datos completos y validos), validaciones de hosts/puertos sin provision, cancelacion sin llamadas ni escrituras, PARADA del almacen nativo de la plataforma sin fallback ni llamada al almacen, fallo del almacen tras provision con mensaje generico, confirmaciones publicas sin `credential_ref` ni label ni secreto, y el secreto ficticio JAMAS presente en mensajes, retornos ni escrituras. Todo offline: sin red, sin DNS, sin disco, sin `os.environ`.

## Constraints

Presupuestos por funcion: ciclomatica <= 12, anidamiento <= 4, lineas <= 120, parametros <= 3. Solo dependencias de `deps_allowed`: `tkinter` y las internas contractuales `src.email.provision_account.provision_email_account` (firma `def provision_email_account(root: str, account_id: str, provider: str, email: str, label: str, secret: str, platform=None, backend=None) -> dict`, ya congelada; despacha por `sys.platform` hacia `wincred`/`keychain`/`secretservice` y se invoca SOLO con los seis primeros argumentos), `src.email.discover_mail_servers.discover_mail_servers` (firma `def discover_mail_servers(email: str, resolver=None) -> dict`, ya congelada; se invoca SOLO con `email`, sin resolver) y `src.email.mail_server_store.store_mail_server_config` (firma `def store_mail_server_config(root: str, account_id: str, config: dict) -> str`, ya congelada; stdlib minima si hiciera falta). La rama CLI vive en `src/email/cli.py` y conserva intactos `search`, `account add`, `account list`, `account setup`, `query`, `sync`, `draft` y `send`. PARAR y reportar si la delegacion en `provision_email_account`, `discover_mail_servers` o `store_mail_server_config` no basta para cubrir el caso del formulario, si el secreto no puede viajar solo en memoria desde el widget hasta provision, si el campo password no puede mostrarse con `show="*"`, si se necesitara pedir al usuario el `account_id`, el proveedor o terminos tecnicos adicionales a los cuatro campos de la seccion avanzada, si el discovery no pudiera ejecutarse sin el password o mas de una vez por sesion de la ventana, si la seccion avanzada no pudiera mostrarse dentro de la MISMA ventana o sus cuatro campos no pudieran validarse con las reglas del almacen de servidores, si se necesitara `input()`, `getpass`, variables de entorno, archivos para el secreto, red directa, navegador, servidor HTTP o `subprocess`, si los mensajes de la ventana no pueden ser genericos sin `credential_ref`, sin el label y sin el secreto, si se necesitara ofrecer un fallback inseguro (env, archivo plano, keyring) en lugar de PARAR cuando el almacen nativo de la plataforma (Credential Manager, Keychain o Secret Service) no este disponible, si la provision tuviera que ejecutarse antes de resolver los servidores o el almacen de servidores antes de la provision, si algun subcomando ya congelado tuviera que cambiar de semantica para agregar `setup-gui`, si los codigos `0`/`1`/`2` no pudieran respetarse, o si el formulario tuviera que escribir algo en disco por su cuenta.