# Sprint 58 — Resolución conservadora de contactos

## Objetivo

Definir cómo un agente convierte una solicitud sobre una persona en una
búsqueda reproducible del CLI.

## Resultado

- Una dirección inequívoca se traduce a `contact:EMAIL`.
- Un nombre ambiguo no se convierte en una identidad inventada.
- El agente presenta candidatos y solicita una dirección concreta.
- La búsqueda continúa siendo local, determinista y basada en los índices OKF.

## Verificación

La prueba congelada comprueba que la skill documente esta frontera de
resolución conservadora.
