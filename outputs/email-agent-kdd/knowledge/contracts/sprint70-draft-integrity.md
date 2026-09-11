---
type: KDD Contract
id: email-agent-sprint70-draft-integrity
objective: Vincular la vista previa con el contenido que se enviara
status: frozen
---

- `send` recalcula el ID sha256 del borrador antes de contactar al SMTP;
- el ID de la ruta, el campo `id` y el contenido normalizado deben coincidir;
- si el contenido cambió, el envío se detiene sin contactar al proveedor;
- el agente usa el mismo `DRAFT_ID` que mostró en la vista previa;
- no se repara ni sobrescribe automáticamente el borrador alterado.
