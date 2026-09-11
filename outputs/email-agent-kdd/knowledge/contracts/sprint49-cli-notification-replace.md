---
type: KDD Contract
id: email-agent-sprint49-cli-notification-replace
objective: Reemplazar reglas solo con confirmacion explicita
status: frozen
---

- crear una regla nueva no requiere confirmación destructiva;
- un nombre existente no puede reemplazarse sin `CONFIRMAR REGLA`;
- el rechazo por falta de confirmación no muta la regla;
- la confirmación debe ser literal y ocupar los argumentos finales;
- el reemplazo autorizado conserva el nombre y actualiza únicamente la consulta.
