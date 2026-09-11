---
type: KDD Contract
id: email-agent-sprint21-first-use
objective: Reducir pasos del primer uso sin degradar la seguridad
status: frozen
---

- `onboard ROOT` ejecuta primero el diagnóstico local.
- Con GUI disponible selecciona `account setup-gui`; sin GUI selecciona `account setup`.
- Un error requerido detiene el flujo sin escribir credenciales.
- El comando no omite validaciones ni confirmaciones.
- La selección del flujo no usa red ni modelos.
