# Índice de conocimiento

* [Definición del proyecto](../DEFINITION.md) - Objetivo, principios y alcance inicial.
* [README](../README.md) - Descripción general y arranque rápido del proyecto.
* [Arquitectura](architecture.md) - Componentes y límites del sistema.
* [Modelo OKF](okf-model.md) - Representación de mensajes, hilos, contactos y adjuntos.
* [Contrato: normalizar correo](contracts/normalize-email.md) - Primer contrato implementable del MVP.
* [Contrato: persistir nodo OKF](contracts/persist-email-okf.md) - Serializa el registro de `normalize_email` a un nodo OKF en una ruta validada.
* [Contrato: extraer contactos](contracts/extract-contacts.md) - Deduplica por email los headers From, To y Cc del registro normalizado para nodos `Email Contact`.
* [Contrato: buscar nodos](contracts/search-email-nodes.md) - Busqueda determinista AND de terminos en archivos `.md` bajo una raiz, sin distinguir mayusculas.
* [Contrato: crear borrador](contracts/create-draft.md) - Construye un borrador serializable con `id` determinista, estado `pending` y destinatarios normalizados, sin enviar nada.
* [Contrato: confirmar borrador](contracts/confirm-draft.md) - Confirma un borrador `pending` con la frase exacta `CONFIRMAR ENVIO`, devolviendo una copia `confirmed` con `confirmation_hash` determinista, sin enviar nada.
* [Contrato: persistir nodo OKF en ruta](contracts/persist-email-okf-at.md) - Escribe el registro normalizado como nodo OKF bajo una raíz explícita recibida.
* [Contrato: guardar contactos](contracts/store-email-contacts.md) - Persiste una libreta de contactos deduplicada y determinista bajo una raíz explícita recibida.
* [Contrato: clave de conversación](contracts/conversation-key.md) - Deriva una clave de conversación estable y segura para ruta a partir de un record de email.
* [Contrato: persistir índice de conversación](contracts/persist-conversation-index.md) - Persiste el índice Markdown de una conversación derivado del record mediante `conversation_key`.
* [Contrato: guardar cuentas](contracts/store-email-account.md) - Guarda y lee registros de cuentas de correo en un store JSON local seguro.
* [Contrato: resolver credencial](contracts/resolve-credential.md) - Resuelve una referencia `env://` al secreto de su variable de entorno sin exponerlo.
* [Contrato: obtener mensajes IMAP](contracts/fetch-imap-messages.md) - Lee en modo solo lectura los mensajes de un buzón IMAP como registros parseados.
* [Contrato: parsear email crudo](contracts/parse-raw-email.md) - Convierte un mensaje RFC 5322 crudo en un registro serializable persistible como OKF.
* [Contrato: enviar SMTP](contracts/send-smtp-message.md) - Envía un correo ya confirmado por SMTP devolviendo un recibo serializable.
* [Contrato: política de adjuntos](contracts/attachments-policy.md) - Reglas de adjuntos para el MVP.
* [Contrato: CLI accounts](contracts/cli-accounts.md) - Extiende la CLI local de correo con el subcomando `account`.
* [Contrato: CLI sync](contracts/cli-sync.md) - Extiende la CLI local de correo con el subcomando `sync` que sincroniza una cuenta guardada.
* [Contrato: cursor de sincronización](contracts/sync-cursor.md) - Mantiene por cuenta un cursor UID local para descargar solo mensajes nuevos en ejecuciones posteriores.
* [Contrato: CLI draft y send](contracts/cli-send.md) - Añade los subcomandos `draft` y `send` a la CLI de email con confirmación explícita y sin exponer secretos.
* [Contrato: conexión de proveedores](contracts/provider-connection.md) - Contrato de conexión de proveedores de correo: límites actuales y OAuth futuro.
* [Contrato: extraer temas](contracts/extract-topics.md) - Deriva etiquetas de tema deterministas desde el asunto del record, sin leer el cuerpo ni usar red o modelo externo.
* [Contrato: persistir índice de temas](contracts/persist-topic-index.md) - Persiste los nodos Markdown de temas en `root/store/topics/<topic>.md` delegando en `extract_topics`.
* [Contrato: buscar en email](contracts/query-email.md) - Consulta determinista sobre los registros de email persistidos.
* [Contrato: CLI query](contracts/cli-query.md) - Añade el subcomando `query` a la CLI de email para buscar sobre el store local.
* [Contrato: leer nodo de email](contracts/read-email-node.md) - Lee y valida un nodo OKF de email persistido en Markdown devolviendo su record serializable.
* [Contrato: CLI account setup](contracts/cli-account-setup.md) - Añade el asistente interactivo `account setup ROOT` que configura una cuenta en cuatro preguntas sin pedir nunca la contraseña.
* [Contrato: cargar contactos](contracts/load-email-contacts.md) - Lee la libreta de contactos guardada en `<root>/contacts.json` sin escribir nada; store ausente equivale a libreta vacía.
* [Contrato: CLI contact list](contracts/cli-contact-list.md) - Añade el subcomando `contact list ROOT` a la CLI de email, imprimiendo una línea JSON por contacto (solo `name` y `email`).
* [Contrato: contactos salientes](contracts/extract-outgoing-contacts.md) - Deriva contactos deduplicados del destinatario `to` de un mensaje saliente confirmado, compatible con `store_email_contacts`.
* [Contrato: credencial Windows](contracts/store-windows-credential.md) - Guarda y resuelve secretos en Windows Credential Manager via `wincred://<label>` con backend inyectable; el secreto solo vive en memoria.
* [Contrato: provisión de cuenta Windows](contracts/provision-windows-account.md) - Aprovisiona una cuenta local: valida entradas, guarda el secreto solo en Credential Manager via `store_windows_credential` y persiste en `accounts.json` la ref `wincred://` con `create_email_account` + `save_email_account`; devuelve solo el registro público.
* [Contrato: CLI account setup GUI](contracts/cli-account-setup-gui.md) - Añade el subcomando `account setup-gui ROOT` con un formulario tkinter local que entrega el secreto solo en memoria a `provision_windows_email_account` sin exponerlo.
* [Contrato: descubrir servidores de correo](contracts/discover-mail-servers.md) - Deriva el dominio del correo del usuario y descubre IMAP/SMTP con resolver inyectable, mapa de proveedores conocidos y candidatos confirmados; PARAR con `ValueError` si nada se confirma.
* [Contrato: guardar servidores de correo](contracts/store-mail-servers.md) - Persiste en `root/.email-agent/mail-servers.json` la configuracion publica IMAP/SMTP por cuenta (solo hosts y puertos, jamas secretos) con JSON determinista y escritura atomica; carga ausente `None`, corrupta `RuntimeError`.
* [Contrato: destinatario real de entrega](contracts/delivery-recipient.md) - Extrae verbatim de `Delivered-To`/`X-Original-To`/`Envelope-To` las direcciones de entrega (sin colapsar puntos, `+tag` ni minusculas), alimenta `delivered_to` del registro y el filtro `para:EMAIL` de `query`.
* [Contrato: CLI sync con pagina limitada](contracts/cli-sync-limit.md) - Anade la opcion `--limit N` (1..100) al subcomando `sync` para procesar una pagina IMAP limitada por ejecucion, continuando buzones grandes en ejecuciones posteriores via el cursor UID sin duplicados y sin alterar el uso actual.
