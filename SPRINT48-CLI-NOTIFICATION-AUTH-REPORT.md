# Sprint 48 — Confirmación ejecutable de reglas

## Objetivo

Hacer efectiva en el CLI la barrera de autorización definida para eliminar
reglas de notificación.

## Resultado

- `notification list ROOT` continúa siendo de solo lectura.
- `notification delete ROOT NAME` sin confirmación no modifica el almacén.
- El borrado requiere exactamente `CONFIRMAR REGLA` como argumentos finales.
- La prueba congelada cubre rechazo, no mutación, borrado autorizado y listado.

## Verificación

La batería local debe validar el contrato completo antes de publicar el cambio.
