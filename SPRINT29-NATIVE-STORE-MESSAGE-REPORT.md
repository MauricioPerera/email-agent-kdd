# Sprint 29 — Advertencia localizada del almacén seguro

## Objetivo

Completar la localización del formulario con el mensaje de detención cuando el
almacén nativo del sistema no está disponible.

## Resultado

- La advertencia se muestra en el idioma efectivo.
- Conserva el principio de detenerse: no hay fallback a texto plano ni a
  variables de entorno.
- Nombra el almacén correspondiente al sistema operativo.
- El idioma desconocido vuelve de forma segura a español.

## Verificación

La prueba congelada comprueba la variante inglesa y la batería existente sigue
validando el comportamiento de parada en las tres plataformas.
