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
* [Matriz de plataformas](../../PLATFORM-MATRIX.md) - Instalación y capacidades por sistema operativo.
* [Contrato del Objetivo 14](contracts/sprint14-platform-matrix.md) - Guía multiplataforma para usuarios finales.
* [Informe de instaladores guiados](../../SPRINT15-INSTALLER-REPORT.md) - Detección de Python y pip antes de instalar.
* [Contrato del Objetivo 15](contracts/sprint15-installers.md) - Requisitos y mensajes accionables del instalador.
* [Informe de diagnóstico](../../SPRINT16-DIAGNOSTICS-REPORT.md) - Revisión local previa a configurar una cuenta.
* [Contrato del Objetivo 16](contracts/sprint16-diagnostics.md) - Comando `doctor` seguro y accionable.
* [Informe de reparación guiada](../../SPRINT17-DOCTOR-REPAIR-REPORT.md) - Instrucciones sin cambios automáticos.
* [Contrato del Objetivo 17](contracts/sprint17-doctor-repair.md) - Reparación guiada segura.
* [Informe de reporte seguro](../../SPRINT18-DIAGNOSTIC-REPORT-REPORT.md) - Exportación sin datos sensibles.
* [Contrato del Objetivo 18](contracts/sprint18-diagnostic-report.md) - Reporte local y atómico.
* [Informe de reportes multilingües](../../SPRINT19-MULTILINGUAL-REPORT-REPORT.md) - JSON y texto en tres idiomas.
* [Contrato del Objetivo 19](contracts/sprint19-multilingual-reports.md) - Formatos legibles y estables.
* [Informe de preferencia de idioma](../../SPRINT20-LANGUAGE-PREFERENCE-REPORT.md) - Configuración local en tres idiomas.
* [Contrato del Objetivo 20](contracts/sprint20-language-preference.md) - Idioma efectivo y seguro.
* [Informe de primer uso](../../SPRINT21-FIRST-USE-REPORT.md) - Selección automática de GUI o terminal.
* [Contrato del Objetivo 21](contracts/sprint21-first-use.md) - Onboarding sin degradar seguridad.
* [Informe de errores del onboarding](../../SPRINT22-ONBOARDING-ERRORS-REPORT.md) - Cancelación y siguientes pasos.
* [Contrato del Objetivo 22](contracts/sprint22-onboarding-errors.md) - Resultados accionables y seguros.
* [Informe de onboarding multilingüe](../../SPRINT23-ONBOARDING-I18N-REPORT.md) - Mensajes del primer uso en tres idiomas.
* [Contrato del Objetivo 23](contracts/sprint23-onboarding-i18n.md) - Idioma efectivo y comandos estables.
* [Informe de resumen del onboarding](../../SPRINT24-ONBOARDING-SUMMARY-REPORT.md) - Confirmación pública y segura del alta.
* [Contrato del Objetivo 24](contracts/sprint24-onboarding-summary.md) - Resumen sin referencias de credencial.
* [Informe del siguiente paso](../../SPRINT25-ONBOARDING-NEXT-STEP-REPORT.md) - Recomendación de primer sync.
* [Contrato del Objetivo 25](contracts/sprint25-onboarding-next-step.md) - Continuidad accionable y localizada.
* [Informe de selección de flujo](../../SPRINT26-ONBOARDING-FLOW-REPORT.md) - GUI o terminal bajo demanda.
* [Contrato del Objetivo 26](contracts/sprint26-onboarding-flow.md) - Selección explícita y segura.
* [Informe del formulario gráfico multilingüe](../../SPRINT27-GUI-I18N-REPORT.md) - Etiquetas en tres idiomas.
* [Contrato del Objetivo 27](contracts/sprint27-gui-i18n.md) - Preferencia local sin alterar seguridad.
* [Informe de mensajes GUI](../../SPRINT28-GUI-MESSAGES-REPORT.md) - Validaciones y estados en tres idiomas.
* [Contrato del Objetivo 28](contracts/sprint28-gui-messages.md) - Mensajes localizados sin datos sensibles.
* [Informe de almacén nativo](../../SPRINT29-NATIVE-STORE-MESSAGE-REPORT.md) - Advertencia localizada y segura.
* [Contrato del Objetivo 29](contracts/sprint29-native-store-message.md) - Detención sin fallback inseguro.
* [Informe de idioma explícito](../../SPRINT30-ONBOARDING-LANGUAGE-REPORT.md) - Selección de idioma en primer uso.
* [Contrato del Objetivo 30](contracts/sprint30-onboarding-language.md) - Preferencia local antes del setup.
* [Informe de seguridad del idioma](../../SPRINT31-ONBOARDING-LANGUAGE-SAFETY-REPORT.md) - Rechazo sin efectos secundarios.
* [Contrato del Objetivo 31](contracts/sprint31-onboarding-language-safety.md) - Validación previa del idioma.
* [Informe del asistente de terminal](../../SPRINT32-TERMINAL-I18N-REPORT.md) - Configuración localizada bajo demanda.
* [Contrato del Objetivo 32](contracts/sprint32-terminal-i18n.md) - Idioma explícito y compatibilidad.
* [Informe de ayuda de setup](../../SPRINT33-SETUP-HELP-REPORT.md) - Opción de idioma visible.
* [Contrato del Objetivo 33](contracts/sprint33-setup-help.md) - Descubribilidad sin cambiar compatibilidad.
* [Informe de onboarding del plugin](../../SPRINT34-PLUGIN-ONBOARDING-REPORT.md) - Guía para agentes.
* [Contrato del Objetivo 34](contracts/sprint34-plugin-onboarding.md) - Comandos y límites de seguridad.
* [Informe de opciones del plugin](../../SPRINT35-PLUGIN-ONBOARDING-OPTIONS-REPORT.md) - Contrato documentado del onboarding.
* [Contrato del Objetivo 35](contracts/sprint35-plugin-onboarding-options.md) - Opciones verificadas para agentes.
* [Informe de recuperación de preferencias](../../SPRINT36-ONBOARDING-PREFERENCE-RECOVERY-REPORT.md) - Fallback seguro ante corrupción.
* [Contrato del Objetivo 36](contracts/sprint36-onboarding-preference-recovery.md) - Preferencias ilegibles sin filtrado.
* [Informe de seguridad de idioma en setup](../../SPRINT37-SETUP-LANGUAGE-SAFETY-REPORT.md) - Validación antes de leer entradas.
* [Contrato del Objetivo 37](contracts/sprint37-setup-language-safety.md) - Rechazo sin efectos secundarios.
* [Informe de setup localizado del plugin](../../SPRINT38-PLUGIN-SETUP-LANGUAGE-REPORT.md) - Ruta directa para agentes.
* [Contrato del Objetivo 38](contracts/sprint38-plugin-setup-language.md) - Sintaxis documentada y compatible.
* [Informe del primer sync del plugin](../../SPRINT39-PLUGIN-FIRST-SYNC-REPORT.md) - Continuidad desde onboarding.
* [Contrato del Objetivo 39](contracts/sprint39-plugin-first-sync.md) - Uso de metadatos públicos sin credenciales.
* [Informe de sync paginado del plugin](../../SPRINT40-PLUGIN-SYNC-PAGINATION-REPORT.md) - Primer lote limitado y cursor.
* [Contrato del Objetivo 40](contracts/sprint40-plugin-sync-pagination.md) - Paginación documentada para agentes.
* [Informe del límite de watch](../../SPRINT41-PLUGIN-WATCH-BOUNDARY-REPORT.md) - Monitoreo activo sin promesas persistentes.
* [Contrato del Objetivo 41](contracts/sprint41-plugin-watch-boundary.md) - Vida del proceso y startup separado.
* [Informe de autorización startup](../../SPRINT42-PLUGIN-STARTUP-CONFIRMATION-REPORT.md) - Persistencia con confirmación inmediata.
* [Contrato del Objetivo 42](contracts/sprint42-plugin-startup-confirmation.md) - Frontera de autorización para agentes.
* [Informe de retiro startup](../../SPRINT43-PLUGIN-STARTUP-REMOVE-REPORT.md) - Deshabilitación con autorización.
* [Contrato del Objetivo 43](contracts/sprint43-plugin-startup-remove.md) - Retiro explícito y verificable.
* [Informe de filtros de notificación](../../SPRINT44-PLUGIN-NOTIFICATION-FILTER-REPORT.md) - Dirección real y ciclo de sync.
* [Contrato del Objetivo 44](contracts/sprint44-plugin-notification-filter.md) - Reglas por destinatario sin normalización indebida.
* [Informe de seguridad de notificaciones](../../SPRINT45-PLUGIN-NOTIFICATION-SAFETY-REPORT.md) - Payload como dato no ejecutable.
* [Contrato del Objetivo 45](contracts/sprint45-plugin-notification-safety.md) - Asuntos sin shell ni interpolación.
* [Informe de reintentos de notificación](../../SPRINT46-PLUGIN-NOTIFICATION-RETRY-REPORT.md) - Avisos deduplicados y controlados.
* [Contrato del Objetivo 46](contracts/sprint46-plugin-notification-retry.md) - Frontera entre avisos y correo.
* [Informe de autorización de reglas de notificación](../../SPRINT47-PLUGIN-NOTIFICATION-AUTH-REPORT.md) - Mutaciones con intención explícita.
* [Contrato del Objetivo 47](contracts/sprint47-plugin-notification-auth.md) - Lectura sin confirmación y cambios autorizados.
* [Informe del CLI para reglas de notificación](../../SPRINT48-CLI-NOTIFICATION-AUTH-REPORT.md) - Confirmación ejecutable antes de borrar.
* [Contrato del Objetivo 48](contracts/sprint48-cli-notification-auth.md) - Frase literal para mutaciones destructivas.
* [Informe de reemplazo de reglas](../../SPRINT49-CLI-NOTIFICATION-REPLACE-REPORT.md) - Cambios protegidos por confirmación.
* [Contrato del Objetivo 49](contracts/sprint49-cli-notification-replace.md) - No sobrescribir reglas silenciosamente.
* [Informe de alcance de confirmación](../../SPRINT50-PLUGIN-NOTIFICATION-CONFIRMATION-SCOPE-REPORT.md) - Autorización de una sola operación.
* [Contrato del Objetivo 50](contracts/sprint50-plugin-notification-confirmation-scope.md) - Sin permisos permanentes ni transferibles.
* [Informe de inspección de reglas](../../SPRINT51-CLI-NOTIFICATION-SHOW-REPORT.md) - Presentación exacta antes de mutar.
* [Contrato del Objetivo 51](contracts/sprint51-cli-notification-show.md) - Consulta segura por nombre.
* [Informe de validación de filtros](../../SPRINT52-NOTIFICATION-FILTER-VALIDATION-REPORT.md) - Reglas imposibles rechazadas antes de guardar.
* [Contrato del Objetivo 52](contracts/sprint52-notification-filter-validation.md) - Validación sin efectos secundarios.
* [Informe de estado de reglas](../../SPRINT53-NOTIFICATION-RULE-STATE-REPORT.md) - Pausar y reanudar sin borrar filtros.
* [Contrato del Objetivo 53](contracts/sprint53-notification-rule-state.md) - Cambios de estado autorizados.
* [Informe de integridad del almacén](../../SPRINT54-NOTIFICATION-RULE-STORE-REPORT.md) - Corrupción detenida de forma segura.
* [Contrato del Objetivo 54](contracts/sprint54-notification-rule-store.md) - Sin avisos parciales ni reparación silenciosa.
* [Informe de integridad del estado](../../SPRINT55-NOTIFICATION-STATE-INTEGRITY-REPORT.md) - Historial protegido ante corrupción.
* [Contrato del Objetivo 55](contracts/sprint55-notification-state-integrity.md) - Detención sin reescritura.
* [Informe de idempotencia de reglas](../../SPRINT56-NOTIFICATION-IDEMPOTENCY-REPORT.md) - No-ops sin escrituras innecesarias.
* [Contrato del Objetivo 56](contracts/sprint56-notification-idempotency.md) - Repetición segura de operaciones.
