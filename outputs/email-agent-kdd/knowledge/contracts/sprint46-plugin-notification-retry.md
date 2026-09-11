---
type: KDD Contract
id: email-agent-sprint46-plugin-notification-retry
objective: Documentar deduplicación y reintentos de avisos
status: frozen
---

- la skill documenta deduplicación por hash de mensaje;
- la skill indica recordar avisos enviados;
- la skill indica reintentar fallidos en el siguiente ciclo;
- el agente no confunde un reintento de aviso con un reenvío SMTP;
- no se reintenta automáticamente un envío de correo incierto.
