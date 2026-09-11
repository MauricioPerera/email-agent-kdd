---
type: KDD Contract
id: email-agent-sprint11-lsfa-interoperability
objective: Validar la interoperabilidad del puente email-agent-kdd con LSFA
status: frozen
---

# Contrato del Objetivo 11

## Criterios de aceptación

- las solicitudes del puente contienen los campos mínimos LSFA;
- ningún campo de solicitud contiene valores de credenciales o contenido real;
- el envío se declara como riesgo alto;
- las confirmaciones requeridas son humanas y de un solo uso;
- un validador local rechaza valores sensibles y confirmaciones reutilizables;
- la prueba no usa red, modelos ni credenciales.

## Evidencia

La evidencia ejecutable está en `tests/frozen_lsfa_integration.py` y el
resumen en `LSFA-INTEROPERABILITY.md`.

Si la validación no puede ejecutarse de forma segura, PARAR y reportar el
bloqueo; no sustituirla por una conexión contra una cuenta real.
