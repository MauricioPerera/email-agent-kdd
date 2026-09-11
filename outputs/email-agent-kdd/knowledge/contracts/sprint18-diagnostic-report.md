---
type: KDD Contract
id: email-agent-sprint18-diagnostic-report
objective: Exportar evidencia de diagnóstico sin datos sensibles
status: frozen
---

- `doctor --report FILE` escribe un JSON local y atómico.
- El reporte excluye `ROOT`, rutas completas, credenciales, variables de entorno y correo.
- El reporte contiene únicamente checks, estado, siguiente paso y reparaciones propuestas.
- La exportación no usa red ni envía el archivo.
- Un fallo de escritura devuelve un error genérico y no deja temporales.
