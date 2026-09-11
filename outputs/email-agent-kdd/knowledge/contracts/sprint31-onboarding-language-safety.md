---
type: KDD Contract
id: email-agent-sprint31-onboarding-language-safety
objective: Rechazar idiomas inválidos sin efectos secundarios
status: frozen
---

- un idioma fuera de `es`, `en` o `pt` devuelve error de argumentos;
- la validación ocurre antes de diagnóstico, setup o escritura;
- el error indica los idiomas aceptados sin incluir secretos;
- una preferencia existente no se modifica ante un idioma inválido;
- no se abre GUI ni se inicia el asistente de terminal.
