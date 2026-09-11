# Objetivo 19 — Reportes legibles y multilingües

El diagnóstico ahora permite exportar JSON o texto y seleccionar español,
inglés o portugués:

```text
email-agent doctor --lang es --format text --report diagnostico.txt
email-agent doctor --lang en --format json --report diagnostics.json
email-agent doctor --lang pt --format text --report diagnostico.txt
```

El JSON mantiene nombres de checks estables para agentes. El texto está pensado
para compartirlo con una persona y usa etiquetas comprensibles. Ningún formato
incluye credenciales, rutas completas, variables de entorno o contenido de
correo; la exportación tampoco se envía automáticamente.
