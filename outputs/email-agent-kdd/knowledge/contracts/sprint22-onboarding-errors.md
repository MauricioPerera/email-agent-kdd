---
type: KDD Contract
id: email-agent-sprint22-onboarding-errors
objective: Comunicar cancelación y siguientes pasos del primer uso
status: frozen
---

- requisitos pendientes incluyen una acción `email-agent doctor --fix`;
- cancelación o fallo de setup devuelve código distinto de cero y un siguiente paso;
- onboarding no reintenta ni confirma operaciones automáticamente;
- los mensajes no incluyen secretos, rutas completas ni contenido de correo;
- el usuario puede volver a ejecutar `onboard ROOT` de forma segura.
