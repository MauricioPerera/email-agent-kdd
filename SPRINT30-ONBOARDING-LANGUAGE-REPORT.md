# Sprint 30 — Idioma explícito del primer uso

## Objetivo

Permitir seleccionar el idioma de todo el onboarding sin depender de la
configuración regional del sistema.

## Resultado

- `onboard ROOT --lang es|en|pt` valida y guarda la preferencia local.
- El idioma elegido se aplica al diagnóstico, GUI o terminal y resumen final.
- El idioma del sistema sigue siendo el valor predeterminado si no se indica.
- Un idioma inválido detiene el flujo antes de abrir configuración.

## Verificación

Se añadió una prueba congelada que valida persistencia y uso de portugués.
