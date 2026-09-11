---
type: KDD Contract
id: email-agent-sprint64-contact-find-json
objective: Exponer candidatos de contacto en JSON
status: frozen
---

- `contact find ROOT TEXT --json` devuelve un objeto JSON;
- el objeto contiene `total` y `results`;
- cada resultado solo contiene `name` y `email`;
- la búsqueda no muta la libreta;
- múltiples candidatos no autorizan elegir automáticamente.
