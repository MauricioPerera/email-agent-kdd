# Sprint 3 — Diseño de adjuntos (metadatos hoy, contenido optativo mañana)

## Resumen

Hoy el pipeline extrae y persiste únicamente **metadatos** de adjuntos (`filename`, `content_type`, `size`, `sha256`) en el nodo OKF del mensaje; los bytes nunca se guardan. Este sprint define el diseño para añadir, de forma **optativa** y bajo autorización explícita del usuario, la extracción y el almacenamiento de contenido de adjuntos en disco, su asociación estable al mensaje/conversación, y comandos de listar/descargar con errores sanitizados. Nada de este diseño cambia el comportamiento por defecto: sin autorización, el sistema sigue guardando solo metadatos.

## Estado actual

- `src/email/parse.py` (`_attachments`): recorre las hojas del MIME, filtra por `get_filename()` no nulo, decodifica el payload para calcular `size` y `sha256`, y descarta los bytes inmediatamente después. El filename se toma crudo (sin saneamiento ni normalización).
- `src/email/persist.py` (`persist_email_okf`): serializa solo los `sha256` de los adjuntos como lista bajo el frontmatter `attachments:`; ni filename ni content_type ni size llegan al disco. El cuerpo y el frontmatter se escriben atómicamente (`.tmp` + `replace`) y rechaza sobrescribir contenido distinto.
- `src/email/imap_reader.py` (`fetch_imap_messages`): obtiene el mensaje completo con `FETCH (RFC822)`, es decir, los bytes de los adjuntos ya viajan por red en cada sincronización aunque luego se descarten; el parseo se delega íntegramente en `parse_raw_email`.
- README y SKILL.md: la política documentada es "conservar metadatos y hashes, aplazar la extracción hasta que el usuario la pida; no subir ni enviar adjuntos implícitamente".

Consecuencia: hoy es imposible descargar un adjunto de un mensaje ya sincronizado (los bytes no están en el store), y re-extraerlo requeriría re-descargar el mensaje completo del servidor.

## Contrato OKF

El nodo actual solo lista hashes. Para que "listar/descargar" sea posible sin reparsear el RFC822, el frontmatter del mensaje se amplía así:

- `attachments:` — lista de entradas, cada una con:
  - `sha256` (ya existe; pasa a ser la **clave de asociación** con el blob).
  - `filename` (crudo, tal como llegó; se muestra siempre saneado).
  - `content_type`.
  - `size` (bytes del payload decodificado).
  - `part_index` (índice de la parte MIME hoja dentro del mensaje, para desambiguar dos adjuntos con el mismo hash/filename en un mismo mensaje).
- `attachments_stored: true|false` (o por-entrada `stored: true`) — marca si el blob ya está en disco. Sin este campo, un `sha256` listado no garantiza descargabilidad.

Regla de compatibilidad: `persist.py` actual escribe solo hashes. La versión nueva debe aceptar el formato antiguo (lista de strings) y el nuevo (lista de mapas) tanto al leer como al escribir, para no romper stores existentes. El orden de la lista es determinista (orden de aparición en el MIME) y sirve como índice estable junto a `part_index`.

## Almacenamiento optativo (layout)

Layout propuesto, análogo al papelera local `.trash`:

- `ROOT/attachments/ab/cd/<sha256>` — blob binario inmutable, direccionado por contenido, con `ab` y `cd` los dos primeros bytes hex del hash (evita directorios planos enormes).
- `ROOT/attachments/<sha256>.meta` — un registro pequeño (texto/JSON) con filename saneado, content_type, size, cuenta de referencia y fecha de extracción. El filename **crudo** no se usa como ruta, solo como dato.
- La extracción ocurre en uno de dos momentos: (a) durante `sync` si el usuario activa `--attachments` (con límites aplicados), o (b) bajo demanda con el comando de descarga, re-fetch del mensaje por UID.

Decisión de diseño clave: el blob es **compartido por contenido** (content-addressed). Dos mensajes con el mismo adjunto apuntan al mismo blob; el borrado de un mensaje no borra el blob salvo GC explícito con conteo de referencias.

## Límites y tipos

- Tamaño máximo por adjunto configurable (propuesto por defecto: 25 MB), y presupuesto máximo total por `sync` (propuesto: 100 MB o N adjuntos, lo que ocurra antes). Los adjuntos que exceden el límite se registran como metadatos con `stored: false` y un motivo (`skipped: size-limit`), nunca se truncan.
- Tipos permitidos por lista de configuración (`attachments.allow`); por defecto se rechazan tipos de alto riesgo para ejecución posterior (`application/x-msdownload`, `application/x-sh`, `.exe/.scr/.lnk/.bat/.cmd/.js` por extensión) — se guardan solo metadatos, nunca bytes, salvo que el usuario autorice explícitamente ese tipo.
- El cálculo de `size`/`sha256` ya existe; la extracción reutiliza exactamente ese payload decodificado para que hash y blob coincidan siempre con lo que el frontmatter declara.

## Seguridad: traversal y colisiones

- **Traversal:** el filename del correo es dato no confiable. Nunca se compone una ruta con él. La ruta del blob se deriva únicamente del `sha256` (hex, 64 caracteres, validado como `[0-9a-f]{64}`). El nombre saneado se calcula aplicando el mismo criterio que `persist._resolve_safe` ya usa para rutas: rechazo de rutas absolutas, `~`, segmentos `..` y resolución fuera de la raíz; para display se conservan solo el nombre base, se neutralizan separadores y caracteres de control, y se limita la longitud. Si el filename está vacío o es ambiguo, se usa `attachment-<n>` con `n = part_index`.
- **Colisiones:** al escribir un blob, si el destino ya existe se verifica que el archivo en disco tenga exactamente el tamaño y hash declarados; si no coincide, se registra `corrupt` y se aborta sin sobrescribir (mismo principio que `persist_email_okf` ya aplica con su rechazo de sobrescritura distinta). Una colisión real de SHA-256 se trata como corrupción, no como dato nuevo. Antes de aceptar un blob se re-verifica el hash del contenido escrito (lectura de vuelta) para cerrar la brecha escritura/verificación.
- Extensiones dobles y Unicode homoglífico solo afectan al nombre de display, nunca a la ruta, así que no pueden provocar escape del directorio ni suplantación de binario.

## Asociación mensaje ↔ conversación

- El vínculo mensaje → adjunto es la lista del frontmatter con `sha256` + `part_index`; el vínculo adjunto → mensajes se resuelve con un índice invertido (`sha256 → lista de nodos .md`) generado escaneando los frontmatter del store (determinista, sin dependencias).
- En conversaciones (`conversation:` en query), el adjunto se muestra en el mensaje concreto; un adjunto reenviado varias veces aparece en cada mensaje pero comparte blob. La vista de conversación puede agregar "adjuntos de la conversación" deduplicados por hash.
- El `message_id` / `in_reply_to` / `references` ya existen en el registro; no se duplican en el adjunto. La trazabilidad completa es: mensaje (nodo .md) → entrada de adjunto (frontmatter) → blob (`ROOT/attachments/...`).

## Idempotencia

- Extraer dos veces el mismo adjunto produce el mismo blob (mismo hash, misma ruta): la segunda extracción es un no-op si el hash verificado coincide.
- `persist.py` mantiene su garantía actual: escribir el nodo con contenido idéntico es un no-op; con contenido distinto, error. Las entradas de adjunto nuevas se insertan en orden determinista para que re-syncs no alteren el frontmatter innecesariamente.
- El índice invertido y el `.meta` son reconstruibles desde el store y los blobs: cualquier derivado puede regenerarse sin perder verdad.
- El re-fetch por UID para descarga bajo demanda es de solo lectura (la capa IMAP ya conecta `readonly=True`) y no muta el cursor ni el store salvo la adición del blob y su marca `stored: true`.

## API / CLI (listar y descargar, con autorización)

- `email-agent attachment list ROOT REL_PATH` — lista los adjuntos del nodo: filename saneado, tipo, tamaño, hash (truncado en display), y estado `stored|not-stored`. Solo lectura, sin autorización especial (los metadatos ya son visibles vía `read`).
- `email-agent attachment download ROOT REL_PATH INDEX DEST` — extrae el adjunto `INDEX` (o por hash con `--sha`) a `DEST`, con: verificación de que el nodo pertenece al store (resolución segura de `REL_PATH`), validación de tipo/extension contra la lista permitida, límite de tamaño, y re-verificación del hash tras escribir. `DEST` se resuelve con la misma política anti-traversal de `_resolve_safe`.
- Autorización: **extraer contenido es una acción con efecto externo local persistente**. El primer `download` (o `sync --attachments`) requiere confirmación explícita del usuario en la conversación (análogo a `startup install`); un agente puede preparar el comando pero no activar la extracción por iniciativa propia, ni para tipos prohibidos aunque el usuario sea ambiguo. La frase de confirmación es distinta de las existentes (`CONFIRMAR ENVIO`, `CONFIRMAR BORRADO PERMANENTE`); propuesta: `CONFIRMAR EXTRACCION` — y nunca se completa por el agente.
- `email-agent attachment gc ROOT` (optativo, fuera de alcance mínimo): borra blobs sin referencias tras listarlos; requiere confirmación porque es destructivo y no pasa por `.trash` en su primera versión (candidato a integrarse con el ciclo `.trash` del sprint 2).

## Errores sanitizados

- Mismo estándar que la capa IMAP: tipo de excepción + mensaje, sin rutas de credenciales, sin secretos, y sin rutas de usuario completas cuando el mensaje puede acabar en un log compartido (se muestra la ruta relativa a `ROOT`).
- Códigos de salida alineados con los comandos remotos: `0` éxito (recibo JSON en stdout), `1` fallo de operación, `2` error de argumentos.
- Errores nominales: `attachment-not-found`, `attachment-not-stored` (blob ausente; sugiere `download` bajo demanda), `size-limit-exceeded`, `type-not-allowed`, `hash-mismatch` (blob corrupto o colisión), `unsafe-path` (traversal en `DEST`), `confirmation-required`.
- Ningún error imprime el filename crudo si contiene caracteres de control: se sanea también en la salida de error.

## Pruebas offline

Sin red, sin IMAP, con fixtures RFC822 embebidos (mismo patrón que los `frozen_*` existentes):

1. Parseo con adjuntos múltiples, mismo filename, mismo contenido repetido → entradas con `part_index` distintos y hashes iguales.
2. Filenames hostiles: `../../evil`, `C:\temp\x`, `~x`, nombre vacío, Unicode y caracteres de control → ruta de blob siempre bajo `ROOT/attachments`, display saneado.
3. Hash verificado: blob existente alterado en un byte → `hash-mismatch`, sin sobrescritura.
4. Límites: adjunto sobre el máximo y presupuesto agotado → `stored: false` con motivo, sin bytes en disco.
5. Tipos prohibidos por defecto → solo metadatos; con tipo autorizado explícitamente → blob.
6. Idempotencia: extraer dos veces → segundo intento no-op; persistir el nodo dos veces → sin diff.
7. Compatibilidad de frontmatter: nodo con formato antiguo (solo hashes) se lee y se actualiza sin perder datos.
8. `list` sobre nodo sin adjuntos, con adjuntos no almacenados y con formato mixto → salida estable.
9. Sanitización de errores: inyectar fallo de disco/permiso → mensaje sin rutas absolutas ni secretos, código `1`.
10. Índice invertido: reconstrucción desde store, deduplicación por hash, y baja de referencia tras `message delete`/`purge` (respetando `.trash`).

## Preguntas

1. ¿Confirmación por comando (`download`/`sync --attachments`) o una sola vez por cuenta (flag persistente en el store de la cuenta)?
2. ¿Frase literal para extracción: `CONFIRMAR EXTRACCION` o preferís reutilizar el patrón de dos tokens como en envío/purga?
3. ¿Los blobs comparten el ciclo `.trash` (mover blob a `.trash` cuando el último mensaje que lo referencia se purga) o GC separado?
4. ¿Presupuesto por defecto de `sync --attachments` (propuesto 100 MB / sync) y tamaño máximo por adjunto (propuesto 25 MB)?
5. ¿Se extraen adjuntos de mensajes ya sincronizados vía re-fetch por UID, o solo los mensajes futuros? (El re-fetch añade tráfico pero evita re-sincronizar todo.)
6. ¿`part_index` como clave de desambiguación es suficiente, o hace falta un ID de adjunto estable independiente?