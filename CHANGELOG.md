# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato se inspira en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
la versión sigue [SemVer](https://semver.org/lang/es/). La release pública actual
es `0.2.2`, y coincide con `pyproject.toml` (`email-agent-cli`) y con
`plugins/email-agent/.codex-plugin/plugin.json`.

## [Unreleased]

## [0.2.2] — 2026-09-20

### Corregido

- La configuración verifica que IMAP pueda abrir `INBOX` antes de guardar la
  cuenta; un inicio de sesión parcial ya no se presenta como configuración
  válida.
- La persistencia bajo raíces absolutas funciona correctamente en Windows,
  incluso cuando el archivo destino todavía no existe.
- Los instaladores, el plugin, el marketplace y el prompt público apuntan a
  esta release corregida.
- Se añadieron pruebas de regresión para la selección del buzón y las rutas
  absolutas de Windows.

## [0.2.1] — 2026-09-15

### Distribución

- Se publica por primera vez una rueda estable que incluye el flujo reanudable
  `bootstrap` y la interfaz local `send-gui` documentados para agentes.
- El prompt de instalación descarga directamente los wheels publicados y
  `SHA256SUMS.txt`, los valida antes de ejecutar pip y no requiere Git.
- Paquete, plugin, catálogo e instaladores se alinean con `v0.2.1`.

## [0.2.0] — 2026-09-12

### Seguridad y fiabilidad (Sprint 78)

- Verificación TLS explícita en IMAP/SMTP, seguimiento de UIDVALIDITY y rechazo
  de referencias/cursors de generaciones distintas del buzón.
- Estado persistente de envío y exclusión entre procesos. Un resultado SMTP
  incierto no se reenvía automáticamente; requiere una nueva decisión explícita.
- Extracción PDF aislada solo en Linux con Bubblewrap, prlimit y antivirus;
  Windows/macOS fallan de forma cerrada sin ese sandbox.
- Pruebas de instalación y sandbox fuera del checkout, más evidencia CI
  Windows/macOS/Linux con Python 3.10–3.13.

### Distribución

- Versiones del paquete, plugin, marketplace e instaladores alineadas a v0.2.0.
- La release incluye los wheels de pypdf y typing_extensions requeridos por la CLI.
  Los instaladores verifican todos por SHA-256 y los instalan sin recurrir a un índice.
- Nodos IMAP legacy deben re-sincronizarse para obtener su UIDVALIDITY; no se
  deben inventar identidades ni editar el registro de envío para desbloquearlo.

Los cambios posteriores a v0.1.0 incluidos en esta release se detallan abajo.

### Seguridad de adjuntos (Sprint 76 — 2026-09-11)

- `attachment extract` ejecuta un gate antivirus fail-closed antes de decodificar
  texto; ClamAV se consume por stdin y sus estados no exponen contenido.
- Ausencia, infección, timeout o error del scanner detienen la extracción.

### Añadido (Sprint 77 — 2026-09-11)

- Extracción de texto PDF mediante worker sin red, con límites de tamaño, páginas,
  salida y tiempo; los PDF cifrados o corruptos se rechazan.

### Añadido (Sprint 75 — 2026-09-11)

- `attachment extract` convierte localmente blobs almacenados de tipos textuales
  seguros después de la confirmación literal, verificando hash y tamaño.
- Formatos activos y ejecutables continúan rechazados hasta disponer de sandbox y
  antivirus.

### Cambios de distribución (Sprint 74 — 2026-09-11)

- Los instaladores descargan el wheel de `v0.1.0` y verifican su SHA-256 antes de
  instalar; el modo desde repositorio queda explícito para desarrollo.

### Cambios posteriores a la publicación (Sprint 73 — 2026-09-11)

- Los instaladores usan la referencia estable `v0.1.0` por defecto y permiten
  seleccionar otra referencia de forma explícita.

## [0.1.0] — 2026-09-11

### Añadido y corregido (sprints 68–70 — 2026-09-11)

- **Previsualización segura de borradores**: `draft show ROOT DRAFT_ID` permite
  revisar destinatarios, asunto y cuerpo sin red, credenciales ni mutación.
- La salida de la previsualización usa una lista cerrada de campos y no expone
  datos adicionales persistidos.
- `send` verifica la integridad determinista del borrador antes de contactar al
  SMTP y rechaza cambios posteriores a su creación.

### Corregido (sprint 12 — 2026-09-11)

- **Emisión segura de notificaciones de escritorio**: el asunto del correo ya no
  puede interpretarse como código en ninguna plataforma. Windows ejecuta un
  script de PowerShell **constante** vía `-EncodedCommand` y recibe el texto por
  variables de entorno (antes `-Command` re-parseaba la línea, lo que permitía
  ejecutar comandos con un asunto malicioso); macOS usa un AppleScript constante
  con `system attribute` por entorno (antes `%r` interpolaba el asunto en
  AppleScript); Linux pasa el texto a `notify-send` como argumento tras `--`
  (evita inyección de opciones). Nunca hay shell ni concatenación de datos del
  correo en scripts. Un fallo del mecanismo nativo se informa con un error
  genérico, los éxitos se persisten y los fallidos se reintentan en el siguiente
  ciclo; el texto Unicode (emojis, acentos, CJK) llega intacto.

### Corregido (sprint 10 — 2026-09-11)

- **Desvinculación transaccional** (`account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR`):
  ya no es secuencial sin rollback. El orden real es: referencia de cuenta en
  `accounts.json` → configuración pública de servidores en `mail-servers.json` →
  **solo al final** el secreto del almacén nativo. Si un paso falla se restaura el
  estado local previo (rollback best-effort) y el error original se propaga: nunca
  queda un secreto huérfano sin aviso ni se reescriben secretos. Los correos ya
  descargados se conservan byte a byte.

### Añadido (sprint 9 — 2026-09-11)

- **Almacenes de credenciales nativos multi-OS**: Windows Credential Manager
  (`src/email/wincred.py`), macOS Keychain vía CLI `security`
  (`src/email/keychain.py`: stdin-only, sin shell, timeout de 10 s) y Linux
  Secret Service/libsecret vía `secret-tool` (`src/email/secretservice.py`,
  resuelve la asociación multi-cuenta de la sesión D-Bus). Ninguno tiene fallback
  menos seguro: sin almacén, el alta se detiene con un error que nombra el almacén
  que falta. No hay respaldo en texto plano ni en variables de entorno.
- **Formulario GUI multiplataforma** (`account setup-gui`, tkinter): guarda la
  contraseña solo en el almacén nativo del sistema, detecta servidores IMAP/SMTP y
  comprueba autenticación de ambos antes de guardar (la prueba SMTP solo autentica;
  nunca envía un correo). Cancelar o cerrar la ventana no persiste nada.
- **Asistente de terminal** (`account setup`) que nunca pide la contraseña: solo el
  nombre de la variable de entorno que la contiene; funciona igual en los tres
  sistemas.
- Comprobación previa de conexión IMAP/SMTP con mensajes de error genéricos
  (sin contraseñas, `credential_ref`, tracebacks ni datos de conexión).

### Añadido (sprint 8 — 2026-09-11)

- **Onboarding verificable sin red**: pruebas congeladas del asistente de terminal
  (`frozen_onboarding_cli_setup.py`), de la comprobación de conexión con IMAP/SMTP
  falsos (`frozen_onboarding_connection_check.py`) y de la gestión de secretos del
  formulario GUI (`frozen_onboarding_gui_secrets.py`).
- Ajustes menores de onboarding en `src/email/cli.py` y `src/email/gui_setup.py`
  (p. ej. `from builtins import input` para que el parcheo del asistente sea
  estable). Sin cambio de comportamiento.

### Añadido (sprint 7 — 2026-09-11)

- **Validación oficial del manifiesto del plugin** con `validate_plugin.py`:
  `longDescription` movido dentro de `interface`, `skills` en forma de ruta
  (`"./skills"`), `defaultPrompt` como lista (≤ 3 entradas, ≤ 128 caracteres).
  Coherencia mantenida con `.agents/plugins/marketplace.json`,
  `plugins/email-agent/skills/email-agent/SKILL.md` y la prueba congelada
  `frozen_plugin_manifest.py` (formato semver estricto).

### Añadido (sprint 6 — 2026-09-11)

- **Plugin descubrible e instalable por agentes**: metadatos ampliados del
  manifiesto (repository, licencia MIT, keywords), catálogo en
  `.agents/plugins/marketplace.json`, y corrección del prefijo de la ayuda de la CLI
  (`email-agent` en lugar de `email-cli`).
- **Instaladores con verificación**: `installers/install.ps1` (Windows) e
  `installers/install.sh` (macOS/Linux) comprueban que `email-agent --help`
  responde antes de declarar éxito y guían sobre la carpeta (`Scripts`/`bin`) que
  falta en el PATH. No imprimen ni piden secretos.

### Añadido (sprint 5 — 2026-09-11)

- **Auditoría y corrección de release**: configuración pytest unificada en
  `pytest.ini` (`python_files = frozen_*.py`, `testpaths` en
  `outputs/email-agent-kdd/tests`), job de empaquetado `python -m build` en CI
  (sdist + wheel verificados, sin publicar), job de higiene que falla el build si
  `git ls-files` contiene `store/`, `work/`, `drafts/`, `.email-agent/`, `build/`,
  `*.egg-info` o archivos de secretos, y checklist de release en `docs/RELEASE.md`.

### Añadido (sprint 4 — 2026-09-11)

- **`sync --attachments CONFIRMAR EXTRACCION`**: la sincronización guarda los blobs
  de los adjuntos permitidos reutilizando el RFC822 ya descargado en esa misma sync
  (un solo `FETCH (RFC822)` por mensaje, sin re-descarga). Sin la frase el comando
  aborta antes de conectar; sin la opción jamás se persiste un byte de adjunto.
  Presupuesto total por sync de 100 MB configurable con `SYNC_ATTACHMENT_BUDGET_MB`
  (entero ≥ 1). Los excedidos o bloqueados quedan como metadatos con `stored: false`
  y motivo (`skipped: ...`), nunca truncados. Escritura content-addressed, idempotente
  y atómica; un fallo por adjunto se degrada a `skipped` sin abortar la sync.
- **`attachment gc`**: dry-run de solo lectura (`attachment gc ROOT`) que lista en
  JSON blobs sin referencia, corruptos y no reconocidos; con la frase literal
  `CONFIRMAR BORRADO ADJUNTOS` (validada antes de mutar) los elimina junto a su
  `.meta`. Nunca se borra un blob referenciado, corrupto o de forma no reconocida;
  un fallo de E/S detiene todo sin borrar nada más (fail-closed). Idempotente.

### Añadido (sprint 3 — 2026-09-10/11)

- **Metadatos de adjuntos en el frontmatter** del nodo: `filename` saneado,
  `content_type`, `size`, `sha256` y `part_index`; el contenido no se extrae durante
  `sync` por defecto.
- **`attachment list ROOT REL_PATH`** (solo lectura): una línea JSON por adjunto;
  nunca abre blobs ni conecta a IMAP.
- **`attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION`** (autorizado):
  valida el nodo antes de conectar, hace un re-fetch readonly del RFC822 por UID
  (no muta cursor ni store), valida límites (máximo 25 MB por adjunto; tipos y
  extensiones bloqueados por defecto) y guarda el blob content-addressed en
  `ROOT/attachments/ab/cd/<sha256>` con verificación de hash antes y después;
  la copia en `DEST` es relativa a `ROOT`, atómica y re-verificada.
- **Asociación OKF posterior**: marca `stored: true` atómicamente solo en la entrada
  del `part_index` descargado; si falla hay rollback (nodo intacto, sin `.tmp`
  residual, copia en `DEST` retirada). Los nodos legacy no se reescriben en silencio.
- **Vínculo sync → download**: los nodos sincronizados llevan `mailbox`, `imap_uid`
  y `account_id`, lo que hace alcanzable la re-descarga por UID.

### Añadido (sprint 2 — 2026-09-10)

- **Borrado remoto IMAP en la CLI** (`src/email/imap_deletion.py`, abstracción
  `MailDeletionProvider`, implementación `ImapDeletionProvider` con
  `connection_factory` inyectable):
  - `message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX` — `UID COPY` a
    Trash/Papelera + `UID STORE \Deleted` sobre el original, sin expunge.
  - `message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX` —
    mueve el mensaje desde Trash a su mailbox original, también sin expunge.
  - `message remote-purge ROOT ACCOUNT_ID UID MAILBOX CONFIRMAR BORRADO PERMANENTE` —
    `UID EXPUNGE` selectivo solo si el servidor anuncia `UIDPLUS`; si no, aborta
    antes de tocar el buzón para evitar un expunge global.
  - El `TRASH_MAILBOX` es un parámetro obligatorio y explícito (sin autodetección
    vía `LIST` ni valores implícitos); la conexión se libera con `unselect`/`logout`
    (nunca `close`, que expurga en RFC 3501). Recibo JSON en stdout (`0`), `1` ante
    fallo de operación y `2` ante error de argumentos; sin secretos en mensajes.

### Añadido (sprint 1 — 2026-09-10)

- **Borrado reversible del store local** (`src/email/deletion.py`):
  `message delete ROOT REL_PATH` (mueve el nodo a `ROOT/.trash` con manifiesto JSON),
  `message trash ROOT` (lista manifiestos), `message restore ROOT TRASH_REL_PATH`
  (restaura sin sobrescribir) y `message purge ROOT TRASH_REL_PATH
  CONFIRMAR BORRADO PERMANENTE` (borrado definitivo solo con la frase literal).
- **Ciclo de vida de índices** (`index_lifecycle.py`): alta y baja de un nodo en los
  índices Markdown de Conversation y Topic sin reescribir sus módulos de origen.
- **Búsqueda que respeta la papelera**: `query.py` y `search.py` excluyen cualquier
  archivo o índice bajo `ROOT/.trash` de los resultados, conservando firmas.
- Test end-to-end del ciclo completo (sync → delete → restore → purge) con
  IMAP falsos, sin red ni secretos.

### Base (pre-sprints, en `HEAD`)

- CLI `email-agent` con `query`, `search`, `read`, `account`, `contact`, `sync`
  (paginada, read-only), `watch`, `notification`, `startup` (Windows Task
  Scheduler, macOS LaunchAgents, systemd de usuario en Linux), `draft` y `send`
  con confirmación literal `CONFIRMAR ENVIO`; resultado SMTP incierto nunca se
  reintenta automáticamente.
- Store OKF Markdown local con índices de Conversation y Topic, libreta de
  contactos y cursor de sincronización sin duplicados.

## Limitaciones conocidas (en 0.1.0)

- **Python**: requiere 3.10+; CI valida 3.10–3.13 en Windows, macOS y Linux.
  Python 3.14 no está testado.
- **`account setup-gui`** requiere tkinter (incluido con las distribuciones de
  Python habituales; en Linux algunas distros lo empaquetan aparte, p. ej.
  `python3-tk`). No hay alternativa gráfica alternativa ni fallback menos seguro.
- **Linux Secret Service** (`secret-tool`) necesita una sesión de escritorio con el
  daemon activo; sin él el alta se detiene con un aviso que nombra el almacén que
  falta. No existe fallback en texto plano ni en variables de entorno.
- **`remote-purge`** solo funciona con servidores que anuncian `UIDPLUS`; en el
  resto aborta antes de tocar el buzón.
- **El mailbox Trash/Papelera** de los comandos `remote-*` debe pasarse siempre de
  forma explícita: no hay autodetección.
- **Adjuntos**: máximo 25 MB por adjunto; presupuesto total por sync de 100 MB
  (`SYNC_ATTACHMENT_BUDGET_MB`); tipos y extensiones bloqueados por defecto
  (p. ej. `.exe`, `.scr`, `.lnk`, `.bat`, `.cmd`, `.js`).
- **Nodos legacy**: los que no declaran `account_id` + `imap_uid` + `mailbox` o
  usan el formato antiguo de adjuntos (hashes sueltos) se rechazan en
  `attachment download` con indicación de re-sincronizar. No hay migración
  automática de datos.
- **`watch`** tiene un intervalo mínimo de 30 segundos.
- **No hay cifrado del store local**: los nodos `.md` y los blobs de adjuntos en
  disco se guardan en claro bajo el control de permisos del usuario (la
  contraseña de la cuenta nunca está en el store, solo en el almacén nativo).

## Migraciones

- No se han publicado releases previas, por lo que no hay usuarios que migrar.
- Para tiendas locales creadas con el formato antiguo de adjuntos (solo hashes en
  el frontmatter), la vía soportada es re-sincronizar la cuenta
  (`email-agent sync ...`) para regenerar los nodos con el formato nuevo
  (`part_index`, `stored`). No hay conversión en sitio automática.
