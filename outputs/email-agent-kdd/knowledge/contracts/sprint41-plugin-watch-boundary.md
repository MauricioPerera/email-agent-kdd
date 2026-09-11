---
type: KDD Contract
id: email-agent-sprint41-plugin-watch-boundary
objective: Documentar el límite de vida del proceso watch
status: frozen
---

- la skill documenta `watch ROOT ACCOUNT_ID --every 300 --limit 50`;
- la skill indica que watch solo corre mientras el proceso está vivo;
- la skill no promete monitoreo persistente sin `startup`;
- la CLI expone el comando documentado;
- un agente debe explicar la diferencia al usuario.
