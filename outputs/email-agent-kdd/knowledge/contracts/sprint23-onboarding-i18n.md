---
type: KDD Contract
id: email-agent-sprint23-onboarding-i18n
objective: Aplicar la preferencia local de idioma al onboarding
status: frozen
---

- `onboard ROOT` usa el idioma efectivo guardado en `<root>/.email-agent/preferences.json`;
- los resultados bloqueados incluyen `language`, `next` localizado y la acción estable `email-agent doctor --fix`;
- la cancelación o fallo del setup comunica cómo repetir `onboard ROOT` en el idioma efectivo;
- los comandos y valores de configuración se mantienen estables aunque cambie el idioma;
- los mensajes no incluyen secretos, rutas completas ni contenido de correo.
