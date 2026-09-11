---
type: KDD Contract
id: email-agent-sprint45-plugin-notification-safety
objective: Documentar payloads de notificación como datos no ejecutables
status: frozen
---

- la skill indica que el texto se pasa como dato;
- la skill prohíbe interpolación en scripts;
- la skill prohíbe el uso de shell;
- la skill contempla comillas, `$()` y saltos de línea;
- el agente no debe transformar el asunto en código.
