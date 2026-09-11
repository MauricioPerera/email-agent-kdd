---
type: KDD Contract
id: email-agent-sprint32-terminal-i18n
objective: Localizar el asistente de terminal con idioma explícito
status: frozen
---

- `account setup ROOT` conserva español por compatibilidad;
- `account setup ROOT --lang es|en|pt` localiza intro, prompts y errores;
- `onboard ROOT --terminal --lang LANG` pasa la selección al asistente;
- el idioma inválido se rechaza antes de leer entradas o escribir cuentas;
- el flujo nunca imprime secretos ni referencias de credencial.
