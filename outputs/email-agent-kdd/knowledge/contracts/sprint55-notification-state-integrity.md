---
type: KDD Contract
id: email-agent-sprint55-notification-state-integrity
objective: Rechazar estado de notificaciones corrupto sin efectos secundarios
status: frozen
---

- `sent` debe ser una lista de hashes de texto no vacíos;
- un estado inválido detiene la evaluación antes de notificar;
- no se emiten avisos parciales;
- el estado inválido no se reescribe;
- la historia de entregas no se pierde silenciosamente.
