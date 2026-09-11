# Sprint 75 — Extracción segura de texto de adjuntos

## Resultado

Se añadió `attachment extract ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION`.
Opera únicamente sobre blobs locales ya almacenados, comprueba autorización,
tipo textual permitido, hash y límite de 2 MiB para el texto resultante, y escribe
de forma atómica en un destino relativo bajo `ROOT`.

No interpreta formatos activos ni conecta con IMAP. PDF, HTML, ofimática y
ejecutables se rechazan hasta incorporar una etapa separada con sandbox y
antivirus. La asociación y los metadatos OKF permanecen intactos; el nodo sigue
siendo la fuente de trazabilidad mediante `REL_PATH` e `INDEX`.

## Verificación

- pruebas offline con archivos sintéticos y sin credenciales;
- `python -m pytest -q`;
- `python -m compileall -q src`;
- `git diff --check`.

