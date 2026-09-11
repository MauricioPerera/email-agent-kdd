---
type: KDD Contract
id: email-agent-sprint20-language-preference
objective: Configurar y aplicar el idioma preferido en la experiencia local
status: frozen
---

- `language set|get` solo gestiona `es`, `en` y `pt`.
- La preferencia se guarda localmente y contiene únicamente el código de idioma.
- `doctor ROOT` la usa salvo que reciba `--lang` explícito.
- Un idioma no soportado se rechaza sin escribir.
- No se guardan secretos, rutas de correo ni contenido de mensajes.
