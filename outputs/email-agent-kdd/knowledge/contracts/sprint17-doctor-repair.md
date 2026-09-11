---
type: KDD Contract
id: email-agent-sprint17-doctor-repair
objective: Guiar la reparación de requisitos no sensibles sin mutar el sistema automáticamente
status: frozen
---

- `doctor [ROOT] --fix` conserva todas las comprobaciones de solo lectura.
- El resultado incluye acciones específicas por plataforma cuando corresponde.
- `repair.performed` es siempre `false` en esta versión.
- El comando no instala paquetes, no cambia PATH y no toca credenciales.
- El usuario puede ejecutar las instrucciones y repetir el diagnóstico.
