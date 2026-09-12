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

- Windows: última suite registrada, 1061 aprobadas y 6 omitidas por plataforma.
- WSL/Linux: cuatro pruebas de aislamiento aprobadas (red, archivo y variable
  señuelo, memoria, salida y timeout); dos pruebas adicionales de PDF cifrado y
  exceso de páginas aprobadas por separado.
- Skill del plugin validada con quick_validate.py.
- Solo servidores, credenciales y documentos sintéticos locales: sin correo real.

## Pendientes de cierre

- CI remoto Windows/macOS/Linux y verificación del runtime en instalación nueva.
- Revisión de referencias de restauración entre buzones: UID y UIDVALIDITY no son
  transferibles al buzón destino después de COPY.
- Completar contratos, README y corrección de afirmaciones históricas del Sprint 77.
- Contrastar todos los criterios del contrato con evidencia directa y actual;
  un conteo verde local no acredita por sí solo las garantías de seguridad.
