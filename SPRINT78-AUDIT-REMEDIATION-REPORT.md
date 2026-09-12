# Sprint 78 — Reporte de remediación y aceptación

Este reporte relaciona las correcciones con evidencia reproducible. El cierre
operativo se acredita con el CI del commit integrado y el estado de la PR #3;
no se infiere de este documento ni de un conteo de pruebas.

## Evidencia local e implementación

- TLS: transport.py comparte verificación de certificado/hostname y timeout de
  30 segundos. frozen_tls_certificates.py prueba servidores locales con certificado
  no confiable y nombre incorrecto. frozen_transport_loopback.py verifica que un
  servidor sin STARTTLS no recibe AUTH. QUIT fallido no invalida aceptación SMTP.
- Identidad: UID SEARCH/FETCH BODY.PEEK[], UIDVALIDITY y cursores SQLite por
  cuenta/buzón. El JSON heredado se conserva pero no se reutiliza como UID.
  frozen_imap_identity.py prueba expurgación entre páginas y literal ausente;
  frozen_identity_migration.py verifica reconstrucción sin perder anotaciones.
  Descarga y operaciones destructivas rechazan generaciones obsoletas.
- UIDPLUS: comparación exacta bytes/str; ausencia o nombre parecido se rechazan.
  La reproducción inicial dio un fallo con bytes y 18 casos aprobados.
  frozen_imap_deletion.py verifica borrado selectivo, sin EXPUNGE global.
- Envío: reserva SQLite persistente antes de SMTP, sent antes de contactos.
  frozen_send_state.py y frozen_cli_send.py prueban concurrencia, caída real,
  repetición, contactos y reintento explícito. pending es ausencia de reserva;
  sending sobreviviente a caída bloquea el reenvío. unknown solo se reintenta con
  --retry-unknown y CONFIRMAR REENVIO INCIERTO, además de CONFIRMAR ENVIO.
  Nunca se desbloquean sending/sent. SMTP no garantiza exactamente una entrega
  ante desconexión ambigua; no se debe borrar el registro para reintentar.
- PDF: Bubblewrap Linux con namespace de red, archivos restringidos y entorno
  limpio; prlimit limita memoria a 256 MiB, timeout de 15 segundos. Entrada 25 MiB,
  100 páginas, texto 4 MiB durante producción y JSON serializado máximo 24 MiB.
  Antivirus limpio antes del parser. Windows/macOS nativos o backend no disponible
  fallan con pdf-sandbox-unavailable, sin fallback sin aislamiento.

## Resultados registrados

- Auditoría adicional de cursor V2: nueve casos de valores corruptos reproducían
  aceptación indebida (9 fallos, 2 aprobados antes del fix). La lectura ahora
  valida tipo entero y rango UID/UIDVALIDITY, rechazando corrupción sin reescribir
  el archivo. Así un UID fuera del rango IMAP no puede omitir correos en silencio.

- Windows: suite completa, 1073 aprobadas y 6 omitidas por plataforma.
- WSL/Linux: las seis pruebas reales de aislamiento, cifrado y exceso de páginas
  pasaron juntas en 21.75 segundos.
- Envío: 12 pruebas del registro aprobadas, incluida contención entre cuatro
  procesos Python independientes: un ganador, tres bloqueados y estado sending.
- Restauración: prueba con INBOX UIDVALIDITY=123 y papelera UIDVALIDITY=456;
  la referencia 123 se rechaza sin COPY/STORE; la 456 opera sobre la papelera.
- Skill del plugin validada con quick_validate.py.
- Solo servidores, credenciales y documentos sintéticos locales: sin correo real.

## CI, revisión y limitaciones

- CI remoto del commit 0f7e39c aprobado en los dos eventos:
  [PR](https://github.com/MauricioPerera/email-agent-kdd/actions/runs/34702397415)
  y [push](https://github.com/MauricioPerera/email-agent-kdd/actions/runs/34702395259).
  Cada ejecución acredita 12 combinaciones OS/Python (Windows/macOS/Linux,
  Python 3.10–3.13), tres builds y el control de archivos del repositorio.
  Además, el [CI de d243189](https://github.com/MauricioPerera/email-agent-kdd/actions/runs/34702658763)
  aprobó las mismas 12 combinaciones con la prueba de instalación: python -I,
  módulo importado fuera del checkout, directorio temporal y PDF sintético con
  texto esperado. Linux acredita extracción en el sandbox instalado;
  Windows/macOS acreditan rechazo seguro. Linux Python 3.13 registró 1079 pruebas
  aprobadas y `Installed PDF sandbox smoke passed`.
- CI Linux requiere el perfil AppArmor acotado a /usr/bin/bwrap para permitir
  crear namespaces. No se deshabilita AppArmor globalmente ni se comparte red.
  Las pruebas SMTP usan nombre EHLO sintético para evitar dependencia de DNS
  del runner; conexiones, STARTTLS y certificados siguen siendo reales.
- Se corrigieron las afirmaciones históricas de aislamiento del Sprint 77 y se
  documentaron cursor V2, transporte UID y persistencia de identidad en OKF.
  El plugin distingue el reintento explícito de unknown del bloqueo de sending.
- La revisión no-mistakes del commit 2ba3c5b falló antes de analizar código por
  sesión OAuth de Claude vencida (run 01M2B29A0SCNKX1HW9K6SN1TBJ).
  La alternativa de revisión Codex de solo lectura tampoco pudo leer el repo:
  CreateProcessWithLogonW failed: 2. No se desactivó el sandbox del revisor.
  Posteriormente el usuario pidió usar gh y autorizó publicación directa:
  ese flujo ejecutó CI, pero no constituye aprobación de no-mistakes.

## Contraste de aceptación

| Requisito | Evidencia revisada |
| --- | --- |
| Certificado, hostname, STARTTLS y timeout | transport.py, connection_check.py y pruebas transport_security, tls_certificates y transport_loopback: handshake real y ausencia de AUTH sin STARTTLS |
| UID y UIDVALIDITY, páginas/reinicio/migración | imap_reader.py, imap_identity.py, cursor_store.py, identity_migration.py; frozen_imap_identity, frozen_mailbox_cursor, frozen_identity_migration y descarga CLI |
| Borrado selectivo | imap_deletion.py y frozen_imap_deletion: capacidades bytes/str, rechazo sin UIDPLUS y generación obsoleta antes de COPY/STORE |
| Exclusión y estados de envío | send_state.py, smtp_send.py, cli.py; frozen_send_state y frozen_cli_send: procesos concurrentes, caída real, error durante entrega, contactos y reintento confirmado |
| Aislamiento PDF y límites | pdf_sandbox.py, pdf_worker.py, attachments.py; frozen_pdf_sandbox_linux: red, archivo/entorno señuelo, memoria, archivo de salida y timeout; pruebas de extracción para antivirus y escritura |
| Distribución multiplataforma | CI enlazado: 12 combinaciones; installed_pdf_smoke.py verifica origen del módulo, extracción Linux instalada y rechazo en Windows/macOS |
| Documentación honesta | README, contratos Sprint 77/78, cursor y fetch, instrucciones del plugin; limitaciones SMTP y ausencia de sandbox nativo Windows/macOS explícitas |

La revisión no afirma entrega SMTP exactamente una vez ni aislamiento contra
fallos del kernel. Una configuración OS que impide iniciar Bubblewrap causa
rechazo, no extracción degradada. No hubo acceso a correo real en las pruebas.
Condición de cierre operativo: CI aprobado para el último commit e incorporación
del complemento de [PR #3](https://github.com/MauricioPerera/email-agent-kdd/pull/3)
a main. GitHub conserva el commit exacto, los checks y el recibo de integración.
