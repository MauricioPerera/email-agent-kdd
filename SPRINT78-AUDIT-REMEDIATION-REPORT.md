# Sprint 78 — Remediación de auditoría (en curso)

Este reporte sustituye las notas incrementales. No acredita cierre del sprint.

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

## Pendientes de cierre

- CI remoto del commit 0f7e39c aprobado en los dos eventos:
  [PR](https://github.com/MauricioPerera/email-agent-kdd/actions/runs/34702397415)
  y [push](https://github.com/MauricioPerera/email-agent-kdd/actions/runs/34702395259).
  Cada ejecución acredita 12 combinaciones OS/Python (Windows/macOS/Linux,
  Python 3.10–3.13), tres builds y el control de archivos del repositorio.
  El CI instala la CLI y comprueba su entry point; no es una prueba funcional
  de extracción desde el wheel en una instalación Linux sin checkout.
- CI Linux requiere el perfil AppArmor acotado a /usr/bin/bwrap para permitir
  crear namespaces. No se deshabilita AppArmor globalmente ni se comparte red.
  Las pruebas SMTP usan nombre EHLO sintético para evitar dependencia de DNS
  del runner; conexiones, STARTTLS y certificados siguen siendo reales.
- Se corrigieron las afirmaciones históricas de aislamiento del Sprint 77 y se
  documentó el cursor V2; falta revisión final de consistencia documental.
- La revisión no-mistakes del commit 2ba3c5b falló antes de analizar código por
  sesión OAuth de Claude vencida (run 01M2B29A0SCNKX1HW9K6SN1TBJ).
  La alternativa de revisión Codex de solo lectura tampoco pudo leer el repo:
  CreateProcessWithLogonW failed: 2. No se desactivó el sandbox del revisor.
  Posteriormente el usuario pidió usar gh y autorizó publicación directa:
  ese flujo ejecutó CI, pero no constituye aprobación de no-mistakes.
- Contrastar todos los criterios del contrato con evidencia directa y actual;
  un conteo verde local no acredita por sí solo las garantías de seguridad.
