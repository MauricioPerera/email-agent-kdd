---
type: KDD Contract
id: email-agent-sprint37-setup-language-safety
objective: Rechazar idioma inválido antes del asistente de terminal
status: frozen
---

- `account setup ROOT --lang xx` devuelve código de argumentos;
- la validación ocurre antes de `input()`;
- no se crea ni modifica `accounts.json`;
- el error lista `es`, `en` y `pt`;
- no se imprimen secretos ni referencias de credencial.
