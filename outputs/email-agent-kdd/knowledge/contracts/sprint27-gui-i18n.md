---
type: KDD Contract
id: email-agent-sprint27-gui-i18n
objective: Localizar las etiquetas del formulario gráfico seguro
status: frozen
---

- el formulario carga el idioma efectivo de `<root>/.email-agent/preferences.json`;
- título, campos, botones y sección avanzada se muestran en `es`, `en` o `pt`;
- la selección de idioma no altera discovery, validación, provisionamiento ni confirmaciones;
- ningún texto de interfaz incluye una contraseña, secreto o referencia de credencial;
- si no existe preferencia se mantiene el idioma detectado por el sistema.
