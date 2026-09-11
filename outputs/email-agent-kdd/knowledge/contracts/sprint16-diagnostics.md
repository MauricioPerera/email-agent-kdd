---
type: KDD Contract
id: email-agent-sprint16-diagnostics
objective: Diagnosticar requisitos locales antes de configurar el correo
status: frozen
---

- `doctor [ROOT]` es solo lectura y no usa red, modelos ni credenciales.
- Comprueba Python, pip, plataforma y almacén seguro nativo.
- Trata GUI/Tkinter como capacidad opcional porque existe un flujo terminal.
- Devuelve JSON estable y una recomendación accionable.
- Un error requerido devuelve estado `needs_attention` y código distinto de cero.
