# Email Agent v0.2.1

## Incluido

- Primera release compilada que contiene el flujo reanudable `bootstrap` y la
  interfaz de aprobación local `send-gui` descritos en la documentación actual.
- Instalación sin Git: la guía para agentes descarga la rueda de la CLI y las
  ruedas de `pypdf` y `typing_extensions` desde esta release, valida cada
  SHA-256 frente a `SHA256SUMS.txt` y luego instala con `pip --no-index`.
- Paquete, plugin, catálogo e instaladores apuntan a `v0.2.1`.

## Distribución

La release adjunta el wheel de la CLI, su sdist, los wheels de dependencias y
`SHA256SUMS.txt`. Los hashes deben verificarse antes de cualquier instalación;
no se publica en PyPI ni se modifica una release anterior.

## Requisitos y límites

- Python 3.10 o posterior.
- La configuración de cuenta y la sincronización siguen requiriendo
  autorizaciones separadas; la publicación no accede a correo ni credenciales.
- Las acciones de envío, desvinculación, borrado y extracción conservan sus
  confirmaciones explícitas del usuario.
