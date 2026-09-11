---
type: KDD Contract
id: email-agent-sprint29-native-store-message
objective: Localizar la detención por almacén nativo no disponible
status: frozen
---

- `_platform_stop_message` acepta `es`, `en` y `pt`;
- el mensaje nombra Credential Manager, Keychain, Secret Service o sistema no compatible;
- toda variante comunica detención y ausencia de alternativa segura;
- un idioma inválido vuelve a español sin excepción;
- el cambio no introduce fallback inseguro ni modifica el provisionamiento.
