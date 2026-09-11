---
type: KDD Contract
id: email-agent-sprint26-onboarding-flow
objective: Permitir seleccionar GUI o terminal durante el onboarding
status: frozen
---

- `onboard ROOT` conserva la selección automática según los checks;
- `onboard ROOT --gui` solo inicia GUI si el check `gui` está en `ok`;
- `onboard ROOT --terminal` siempre inicia `account setup`;
- un modo inválido devuelve error de argumentos sin iniciar configuración;
- la selección no expone secretos ni modifica las reglas de confirmación.
