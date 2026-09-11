---
type: KDD Contract
id: email-agent-sprint24-onboarding-summary
objective: Confirmar el alta con un resumen público y seguro
status: frozen
---

- una configuración exitosa devuelve `status: configured` y el idioma efectivo;
- el resumen `account` contiene exactamente `account_id`, `provider` y `email`;
- el resumen nunca contiene `credential_ref`, contraseñas, hosts, rutas completas ni contenido de correo;
- cancelación o fallo conserva su código no cero y no emite un resumen de éxito;
- el resumen no altera la persistencia ni vuelve a conectar con el proveedor.
