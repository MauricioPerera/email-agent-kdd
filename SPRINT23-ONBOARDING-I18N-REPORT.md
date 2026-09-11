# Sprint 23 — Onboarding multilingüe

## Objetivo

Aplicar el idioma efectivo guardado localmente a los resultados del comando
`email-agent onboard ROOT`.

## Resultado

- Los bloqueos por requisitos muestran `next` en español, inglés o portugués.
- La respuesta bloqueada incluye `language` y conserva la acción estable
  `email-agent doctor --fix`.
- La cancelación o fallo del formulario muestra el siguiente paso en el idioma
  elegido y permite repetir el comando.
- Los comandos, secretos, rutas completas y contenido de correo no se incluyen
  en los mensajes.

## Verificación

Se cubren los tres idiomas mediante pruebas congeladas, además de la matriz
existente de tests multiplataforma.
