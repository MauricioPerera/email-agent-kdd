---
type: KDD Contract
id: email-agent-sprint47-plugin-notification-auth
objective: Autorizar explícitamente la mutación de reglas de notificación
status: frozen
---

- `notification list` es una operación de solo lectura;
- crear o cambiar una regla requiere una solicitud explícita para esa regla;
- eliminar exige mostrar nombre y consulta exacta;
- eliminar exige confirmación explícita inmediatamente antes de la operación;
- el CLI exige la frase literal `CONFIRMAR REGLA` para eliminar;
- el agente no infiere, amplía, sustituye ni borra filtros por conveniencia;
- una consulta o dirección ambigua detiene la operación y solicita precisión.
