# Sprint 41 — Límite operativo de watch

## Objetivo

Evitar que un agente confunda el monitoreo activo de la CLI con un servicio
persistente del sistema.

## Resultado

- La skill documenta el comando `watch` con intervalo y límite.
- Indica que el proceso debe permanecer vivo.
- Remite a `startup` cuando se solicite persistencia y a sus confirmaciones
  específicas.

## Verificación

La prueba congelada exige el comando y la limitación operativa en la skill.
