# Sprint 26 — Selección explícita del flujo

## Objetivo

Permitir que el usuario fuerce el formulario gráfico o el asistente de
terminal cuando el flujo automático no sea el conveniente.

## Resultado

- `onboard ROOT` conserva la selección automática.
- `onboard ROOT --gui` exige que Tkinter esté disponible.
- `onboard ROOT --terminal` fuerza el asistente de terminal incluso si existe GUI.
- Una GUI no disponible se informa sin iniciar procesos ni tocar credenciales.
- La selección no cambia las confirmaciones ni el almacenamiento seguro.

## Verificación

Se añadieron pruebas congeladas para ambos modos y para el rechazo seguro de
`--gui` sin Tkinter.
