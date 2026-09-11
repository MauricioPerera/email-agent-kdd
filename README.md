# Email Agent

CLI local y orientada a agentes para sincronizar correo por IMAP, guardar conocimiento en Markdown OKF, buscar por conversación, contacto, temática y destinatario real, y enviar únicamente después de una confirmación explícita.

## Instalación (Windows, macOS y Linux)

Necesitas Python 3.10 o superior instalado en tu equipo. Los mismos pasos valen en los tres sistemas: instala, comprueba y crea tu cuenta.

1. **Instala el programa** con el instalador de tu sistema (ambos avisan de lo que hacen y pueden tardar unos minutos):

   ```text
   powershell -File installers\install.ps1        # Windows
   sh installers/install.sh                       # macOS y Linux
   ```

   Alternativa manual (o aislada con `pipx install .`): `python -m pip install .`

2. **Comprueba que quedó instalado** (el instalador ya lo hace al terminar; puedes repetirlo cuando quieras):

   ```text
   email-agent --help
   ```

   Si tu sistema responde que no encuentra `email-agent`, falta una carpeta de Python en el PATH: en Windows es la carpeta `Scripts` de Python; en macOS y Linux es la carpeta `bin`. Añádela al PATH, cierra y vuelve a abrir la terminal y repite el paso 2.

3. **Crea tu primera cuenta** (paso siguiente, con los mismos comandos en los tres sistemas):

   ```text
   email-agent account setup-gui .    # formulario local sencillo
   email-agent account setup .        # asistente en la terminal
   ```

## Instalación como plugin (para agentes)

El repositorio se distribuye como plugin de agente. El manifiesto está en `plugins/email-agent/.codex-plugin/plugin.json` y el catálogo en `.agents/plugins/marketplace.json`; ambos se validan con `python outputs/email-agent-kdd/tests/frozen_plugin_manifest.py`.

Un agente que quiera instalarlo debe: 1) ejecutar el instalador adecuado o `python -m pip install .`; 2) verificar con `email-agent --help`; 3) leer el archivo `plugins/email-agent/skills/email-agent/SKILL.md` (es la guía completa de capacidades); 4) aplicar sus reglas de seguridad: las frases literales `CONFIRMAR ENVIO`, `CONFIRMAR DESVINCULAR`, `CONFIRMAR BORRADO PERMANENTE`, `CONFIRMAR BORRADO ADJUNTOS` y `CONFIRMAR EXTRACCION` las escribe siempre el usuario, nunca el agente. Si la instalación falla, repórtalo al usuario; no cambies el entorno sin su permiso.

## Primer uso

En el formulario (`account setup-gui`) solo se piden tu correo y tu contraseña; los servidores de correo se detectan solos y, si no, se te ofrecen campos sencillos para completarlos. La contraseña se guarda únicamente en el almacén seguro nativo de tu sistema: Windows Credential Manager en Windows, Keychain en macOS (vía `security`) y Secret Service/libsecret en Linux (vía `secret-tool`, que necesita una sesión de escritorio con el daemon activo); si ese almacén no está disponible, el formulario se detiene con un aviso claro de qué almacén falta y no existe alternativa menos segura, ni texto plano ni variable de entorno. La contraseña nunca se guarda en el repositorio ni se envía al agente. Pulsar Cancelar o cerrar la ventana no guarda nada, y ante cualquier error el mensaje es genérico: nunca aparecen contraseñas ni datos de conexión. El asistente de terminal (`account setup`) nunca pide la contraseña: solo el nombre de la variable de entorno que la contiene, por lo que funciona igual en los tres sistemas. El formulario comprueba autenticación IMAP y SMTP antes de guardar y esa comprobación jamás envía un correo.

La sincronización manual usa páginas y cursor:

```text
email-agent sync . CUENTA --limit 50
email-agent sync . CUENTA --unread
```

Para revisar periódicamente:

```text
email-agent watch . CUENTA --every 300 --limit 50
```

## Búsqueda y notificaciones

`query . "para:ventas+cliente@dominio.com"` filtra por la dirección real de entrega. Las reglas locales se crean con `notification add . NOMBRE "para:direccion@dominio.com"`.

Las notificaciones se emiten con el mecanismo nativo de cada sistema (aviso de PowerShell en Windows, `osascript` en macOS, `notify-send` en Linux) **sin shell y sin interpolar el asunto del correo en ningún script**: el texto viaja siempre como dato (variables de entorno en Windows y macOS, argumento tras `--` en Linux), de modo que un asunto con comillas, `$(...)` o saltos de línea se muestra tal cual y jamás se ejecuta. Un fallo del mecanismo nativo se informa con un mensaje genérico; las notificaciones ya emitidas se recuerdan y las fallidas se reintentan en el ciclo siguiente.

## Gestión de cuentas

El alta puede hacerse con el formulario local `email-agent account setup-gui ROOT` o con el asistente de terminal `email-agent account setup ROOT`. Las cuentas vinculadas se consultan con `email-agent account list ROOT`.

El formulario valida los campos y comprueba autenticación IMAP y SMTP antes de guardar. La prueba SMTP solo autentica la cuenta: nunca envía un correo.

Para desvincular una cuenta se requiere una confirmación literal e independiente:

```bash
email-agent account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR
```

La desvinculación elimina la referencia de cuenta, la configuración pública de servidores y el secreto del almacén nativo del sistema (Credential Manager en Windows, Keychain en macOS, Secret Service en Linux); no elimina los correos ya descargados. Es una transacción: el secreto se borra solo al final, cuando la cuenta y la configuración ya quedaron limpias, y si algún paso falla se restaura el estado local (rollback best-effort) sin dejar un secreto huérfano sin aviso. Un agente puede asistir al usuario, pero nunca debe completar esa confirmación por su cuenta.

## Envío

Los mensajes se preparan con `draft`. El comando `send` exige exactamente `CONFIRMAR ENVIO`; un agente nunca debe saltarse esa confirmación ni reintentar un resultado SMTP incierto.

## Papelera (borrado reversible)

Los nodos `.md` del store se mueven a `ROOT/.trash` (nunca se eliminan directamente) con:

```bash
email-agent message delete ROOT REL_PATH
email-agent message trash ROOT
email-agent message restore ROOT TRASH_REL_PATH
email-agent message purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE
```

`delete` escribe un manifiesto JSON con la ubicación original; `restore` devuelve el nodo a su sitio sin sobrescribir; `purge` elimina definitivamente un elemento ya en `.trash` y exige la frase literal exacta `CONFIRMAR BORRADO PERMANENTE`, que un agente nunca debe completar por su cuenta.

## Papelera remota (IMAP)

El borrado reversible en el servidor usa `src/email/imap_deletion.py` (abstracción `MailDeletionProvider`, implementación `ImapDeletionProvider` con `connection_factory` inyectable). Nunca se expurga en el borrado reversible: se usa `UID COPY` al mailbox Trash/Papelera y `UID STORE \Deleted` sobre el original, y la conexión se libera con `unselect`/`logout` (nunca `close`, que expurga en RFC 3501). El mailbox Trash/Papelera (`TRASH_MAILBOX`) es un parámetro obligatorio y explícito: se pasa siempre en el comando (`remote-delete`/`remote-restore`) o como argumento directo del provider, y se valida antes de conectar. No hay autodetección vía `LIST` ni valores implícitos: si falta, es inválido o no es un `str` no vacío sin espacios en bordes, la operación aborta sin tocar el buzón.

```bash
email-agent message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX
email-agent message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX
email-agent message remote-purge ROOT ACCOUNT_ID UID MAILBOX CONFIRMAR BORRADO PERMANENTE
```

`remote-delete` mueve el mensaje remoto a Trash con `UID COPY` + `UID STORE \Deleted` (sin expunge); el mailbox origen lo resuelve el provider (`INBOX` por defecto: el store de servidores solo guarda host/puerto). `remote-restore` mueve el mensaje desde Trash a su mailbox original (también sin expunge). `remote-purge` exige la frase literal exacta `CONFIRMAR BORRADO PERMANENTE` y solo usa `UID EXPUNGE` selectivo si el servidor anuncia `UIDPLUS`; si no lo anuncia, aborta antes de tocar el buzón para evitar un expunge global. La cuenta, el servidor y la credencial se resuelven del store (`account`, `mail_server_store`, `credential_ref`); nunca se aceptan passwords por argumentos ni se imprimen secretos, y la password jamás aparece en los mensajes de error. Los comandos devuelven un recibo JSON en stdout (código `0`), `1` ante fallo de operación y `2` ante error de argumentos. Un agente nunca debe completar la frase de purga por su cuenta.

## Inicio automatico, plataformas y privacidad

El núcleo es multiplataforma. Para reanudar la descarga tras reiniciar el equipo, el CLI incluye adaptadores para Windows Task Scheduler, macOS LaunchAgents y servicios systemd de usuario en Linux:

```bash
email-agent startup status ROOT ACCOUNT_ID
email-agent startup install ROOT ACCOUNT_ID --every 300 --limit 50
email-agent startup remove ROOT ACCOUNT_ID
```

`startup install` modifica la configuración de inicio del sistema y requiere confirmación directa del usuario. El contenido se procesa localmente y los adjuntos se conservan como metadatos hasta que el usuario solicite extracción.

La serialización de los tres formatos es segura ante datos hostiles: en Windows el valor de `/TR` se construye con `subprocess.list2cmdline` (sin contrabarra final antes de la comilla de cierre); en macOS cada valor del plist se escribe escapado con reglas XML (un `<`, `&` o comilla en la ruta no rompe el XML ni inyecta nodos); en Linux cada argumento de `ExecStart` se cita con el escapado propio de systemd (`\\`, `\"`, `%%`). Una raíz con espacios, comillas o Unicode viaja siempre como dato y nunca se interpreta como comando ni markup; los caracteres de control (saltos de línea, tabuladores, NUL) se rechazan con un error de validación antes de escribir nada.

## Adjuntos (listado, descarga y sync autorizado)

La sincronización persiste solo metadatos (`filename`, `content_type`, `size`, `sha256`, `part_index`) en el frontmatter del nodo; no hay extracción de contenido durante `sync` por defecto y no se escriben bytes de adjuntos al disco. El contenido solo entra al store mediante `attachment download` o `sync --attachments`.

### Extracción durante la sincronización (autorizada)

```bash
email-agent sync ROOT ACCOUNT_ID [--limit N] [--unread] --attachments CONFIRMAR EXTRACCION
```

Con `--attachments` (y la frase literal exacta `CONFIRMAR EXTRACCION`, que un agente nunca completa por su cuenta) la sincronización guarda los blobs de los adjuntos permitidos **reutilizando el RFC822 ya descargado en esa misma sync** (un solo fetch por mensaje, sin re-descarga). Sin la frase el comando aborta antes de conectar; sin la opción jamás se persiste un byte. Cada adjunto pasa los mismos límites que la descarga (máximo 25 MB por adjunto; tipos y extensiones bloqueados por defecto): los excedidos o bloqueados quedan como metadatos con `stored: false` y un motivo (`skipped: ...`) en el frontmatter, nunca truncados.

El presupuesto total por sync es de 100 MB, configurable con la env var `SYNC_ATTACHMENT_BUDGET_MB` (entero ≥ 1); los adjuntos que no caben en el presupuesto quedan como metadatos (`skipped: budget-exhausted`). La escritura del blob es content-addressed, idempotente y atómica (`.tmp` + `replace`), sin blobs temporales residuales ante fallos; un fallo por adjunto se degrada a `skipped`, no aborta la sync ni rompe el cursor. Los nodos se escriben en el formato nuevo de adjuntos (con `part_index` y `stored`); el resumen JSON añade `attachments_stored`, `attachments_skipped` y `attachments_errors` solo en esta modalidad.

### Listado (solo lectura)

El listado es solo lectura: imprime una línea JSON por adjunto con nombre de display saneado, tipo, tamaño, hash y estado `stored|not-stored` (según el frontmatter del nodo); nunca abre blobs ni conecta a IMAP.

```bash
email-agent attachment list ROOT REL_PATH
```

Devuelve código `0` con los metadatos en stdout, `1` ante fallo de operación y `2` ante error de argumentos o `REL_PATH` insegura; los mensajes de error no exponen rutas absolutas ni secretos.

### Descarga (autorizada)

```bash
email-agent attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION
```

La extracción es una acción con efecto local persistente: requiere la frase literal exacta `CONFIRMAR EXTRACCION` como último argumento y la autorización explícita del usuario en la conversación; nunca la aporta el agente. Sin ella el comando aborta (`confirmation-required`) antes de conectar o escribir nada.

El comando valida el nodo antes de contactar al servidor: `REL_PATH` se resuelve de forma segura (sin rutas absolutas ni traversal) y el nodo debe declarar `account_id`, `imap_uid` y `mailbox` en su frontmatter; los nodos legacy sin esa tripleta, o con el formato antiguo de adjuntos (hashes sueltos), se rechazan con indicación de re-sincronizar. Después hace un re-fetch readonly del RFC822 por UID (no muta el cursor ni el store), extrae la parte `INDEX`, la valida contra los límites (máximo 25 MB por adjunto; tipos y extensiones bloqueados por defecto, p. ej. `.exe`/`.scr`/`.lnk`/`.bat`/`.cmd`/`.js`) y guarda el contenido de forma content-addressed en `ROOT/attachments/ab/cd/<sha256>` con verificación de hash antes y después de escribir; el blob es idempotente y no se sobrescribe si difiere (`hash-mismatch`). La copia en `DEST` exige una ruta relativa bajo `ROOT` (anti-traversal), se escribe atómicamente y se re-verifica por hash. Al final marca `stored: true` en la entrada del nodo con escritura atómica; si la asociación falla, el nodo queda intacto y la copia en `DEST` se retira.

Los blobs se comparten por contenido: dos mensajes con el mismo adjunto apuntan al mismo blob, y borrar mensajes no borra blobs. La limpieza de blobs huérfanos es explícita con `attachment gc`.

### GC (listado en seco y borrado autorizado)

```bash
email-agent attachment gc ROOT
email-agent attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS
```

`attachment gc ROOT` es un dry-run de solo lectura: escanea los nodos activos bajo `ROOT/store` (excluyendo `.trash`), recolecta los hashes referenciados y lista en un JSON los blobs candidatos sin ninguna referencia bajo `ROOT/attachments` (cada uno con su `.meta` relacionado), además de `corrupt` (blobs cuyo contenido no coincide con su `sha256`) y `unrecognized` (archivos que no siguen el layout del hash); no borra nada. Con la frase literal exacta `CONFIRMAR BORRADO ADJUNTOS` (validada antes de mutar, nunca la aporta el agente) elimina cada blob candidato y su `.meta`.

Garantías: nunca se borra un blob referenciado; la ruta de cada blob se valida contra el layout del hash (`attachments/ab/cd/<sha256>`) y jamás se sigue una ruta derivada del filename; un blob corrupto o no reconocido se reporta y NUNCA se borra; un nodo ilegible o la ausencia del store abortan el escaneo sin borrar nada (fail-closed); los borrados son directos (sin temporales) y ante el primer fallo de E/S se detiene todo — no se borra ningún otro blob y se reporta `failed`. Idempotente: un segundo pase no encuentra candidatos.

Devuelve `0` con el JSON (que lista `candidates` y `deleted`), `1` ante fallo de operación (store ausente, nodo ilegible, confirmación inexacta o fallo de borrado) y `2` ante error de argumentos o `ROOT` inválido; sin rutas absolutas ni secretos en ningún mensaje.

Consulta [SECURITY.md](SECURITY.md) y [docs/RELEASE.md](docs/RELEASE.md) antes de publicar una release.

La propuesta experimental de formularios locales seguros para agentes está en
el repositorio independiente [Local Secure Forms for Agent CLIs](https://github.com/MauricioPerera/local-secure-forms).
