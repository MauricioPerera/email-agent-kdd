---
type: KDD Contract
id: email-agent-sprint30-onboarding-language
objective: Elegir idioma explícito para todo el primer uso
status: frozen
---

- `onboard ROOT --lang es|en|pt` normaliza y guarda la preferencia local;
- el idioma guardado se usa durante diagnóstico, setup y resumen;
- sin `--lang` se conserva la preferencia existente o el idioma detectado;
- un valor inválido aborta antes de iniciar configuración;
- la preferencia no contiene secretos ni datos de correo.
