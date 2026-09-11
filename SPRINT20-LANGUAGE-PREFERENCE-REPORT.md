# Objetivo 20 — Preferencia de idioma

Se agregó una preferencia local configurable:

```text
email-agent language set ROOT es
email-agent language set ROOT en
email-agent language set ROOT pt
email-agent language get ROOT
```

Cuando `doctor ROOT` no recibe `--lang`, usa la preferencia guardada. Sin una
preferencia, detecta el idioma del sistema y usa español como respaldo. La
preferencia solo contiene `es`, `en` o `pt`; no guarda credenciales, rutas de
correo, variables de entorno ni contenido de mensajes.
