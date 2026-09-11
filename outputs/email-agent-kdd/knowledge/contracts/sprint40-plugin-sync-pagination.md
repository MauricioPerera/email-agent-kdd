---
type: KDD Contract
id: email-agent-sprint40-plugin-sync-pagination
objective: Documentar el primer sync con paginación segura
status: frozen
---

- la skill documenta `email-agent sync ROOT ACCOUNT_ID --limit 50`;
- la skill documenta `--unread`;
- la skill indica continuar mediante cursor almacenado;
- el agente no debe procesar buzones grandes sin límite explícito;
- no se solicitan ni infieren credenciales.
