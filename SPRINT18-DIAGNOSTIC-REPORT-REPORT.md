# Objetivo 18 — Reporte de diagnóstico seguro

`email-agent doctor [ROOT] --report FILE` exporta el diagnóstico en JSON para
compartirlo con soporte o con un agente. El archivo contiene estados,
componentes detectados y recomendaciones, pero no incluye el valor de `ROOT`,
rutas completas, credenciales, variables de entorno ni contenido de correo.

La escritura es atómica y elimina el temporal si ocurre un error. El reporte no
se envía automáticamente; el usuario decide si lo comparte y con quién.
