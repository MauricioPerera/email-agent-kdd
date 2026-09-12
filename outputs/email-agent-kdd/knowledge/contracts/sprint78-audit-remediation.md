---
type: KDD Contract
id: email-agent-sprint78-audit-remediation
objective: Corregir los seis hallazgos de la auditoría con evidencia reproducible
status: implemented_pending_integration
---

# Sprint 78 — Corrección de seguridad y fiabilidad

## Objetivo

Corregir identidad IMAP, seguridad del transporte, repetición de envíos,
aislamiento PDF y detección UIDPLUS. El cierre exige pruebas del comportamiento
real y documentación consistente con las garantías implementadas.

## Secuencia y aceptación

1. Transporte seguro (hallazgos 2 y 3): compartir configuración TLS verificada
   entre alta, lectura, envío y borrado. Exigir certificado y hostname válidos,
   STARTTLS antes de autenticar SMTP cuando no se usa TLS implícito y timeouts
   explícitos. Probar con servidores locales: certificado no confiable, hostname
   incorrecto y STARTTLS ausente deben fallar antes de transmitir credenciales.
2. Identidad IMAP (hallazgo 1): usar UID SEARCH y UID FETCH; asociar cursor y
   referencias remotas a cuenta, buzón y UIDVALIDITY. Definir migración de datos
   antiguos que contienen posiciones: no reinterpretarlos como UIDs. Invalidar
   referencias ambiguas y reconstruirlas mediante sincronización verificada.
   Probar expurgación entre páginas, reinicio, cambio de UIDVALIDITY y recuperación
   de adjuntos; ninguna operación destructiva puede usar una referencia obsoleta.
3. UIDPLUS (hallazgo 6): aceptar capacidades bytes y str; mantener borrado selectivo
   y rechazo sin UIDPLUS. Probar ambos tipos y verificar que no se emite EXPUNGE
   global ni se modifica el buzón si falta la capacidad.
4. Envío (hallazgo 5): persistir transiciones pending/sending/sent/unknown con
   exclusión mutua por borrador. Un comando repetido o concurrente no debe reenviar
   un borrador sent o unknown. Registrar aceptación SMTP antes de tareas secundarias;
   un fallo de QUIT no transforma entrega aceptada en fallo de entrega. Probar
   desconexión durante DATA, caída del proceso, concurrencia y fallo de contactos.
   Documentar que SMTP no permite garantizar entrega exactamente una vez tras una
   desconexión ambigua; cualquier reenvío de un resultado incierto exige una nueva
   decisión explícita del usuario.
5. PDF (hallazgo 4): elegir y documentar aislamiento efectivo antes de habilitar
   extracción: bloqueo de red, acceso restringido a archivos, entorno sin secretos,
   memoria máxima explícita de 256 MiB y finalización en 15 segundos. Limitar entrada
   a 25 MiB antes de leerla completa y salida a 4 MiB durante su producción; máximo
   100 páginas. Antivirus aprobado antes de parsear y escritura atómica al terminar.
   Si el sistema carece del aislamiento requerido, rechazar extracción con un estado
   claro. Probar intentos de red, lectura de un archivo señuelo fuera del aislamiento,
   herencia de variables señuelo, exceso de memoria, salida y timeout. No usar secretos
   reales. Corregir las afirmaciones anteriores de aislamiento no demostrado.

## Flujo KDD

Para cada bloque: reproducir el fallo, actualizar el contrato afectado y registrar
la decisión, implementar la corrección, comprobar la regresión y conservar evidencia.
Los tests simulados deben reflejar las respuestas reales de las bibliotecas; las
garantías de transporte y aislamiento requieren pruebas de integración locales.

## Definición de terminado

- Los seis hallazgos tienen reproducción, corrección y prueba de regresión.
- Migración de cursores y referencias antiguas probada sin pérdida del archivo local.
- Suite completa y CI Windows/macOS/Linux aprobados; las plataformas sin backend
  de aislamiento prueban el rechazo seguro y documentan la limitación.
- README, contratos, instrucciones del plugin y reporte de cierre actualizados.
- Revisión final contrasta cada garantía con su evidencia; no basta el conteo de tests.

## Alcance operativo

Las pruebas usan cuentas, servidores, certificados y documentos sintéticos locales.
No requieren credenciales reales, envíos externos ni borrados de correo del usuario.
No se incorporan nuevos formatos de adjuntos ni funcionalidades ajenas a los hallazgos.
Las correcciones y su evidencia están en SPRINT78-AUDIT-REMEDIATION-REPORT.md.
El cierre operativo exige CI aprobado y la integración del complemento PR #3;
el estado del contrato no sustituye esa verificación.
