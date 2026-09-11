# Sprint 24 — Resumen seguro de configuración

## Objetivo

Confirmar al usuario que `email-agent onboard ROOT` terminó correctamente y
qué cuenta pública quedó vinculada, sin devolver referencias de credenciales.

## Resultado

- Una finalización exitosa emite JSON con `status: configured`, `language` y
  `account`.
- `account` solo contiene `account_id`, `provider` y `email`.
- La salida nunca incluye `credential_ref`, contraseñas, hosts, rutas completas
  ni contenido de correo.
- Una cancelación mantiene código no cero y el mensaje localizado del Sprint
  23.

## Verificación

Se añadió una prueba congelada que comprueba la forma exacta del resumen y la
ausencia de la referencia de credencial.
