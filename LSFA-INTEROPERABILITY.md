# Interoperabilidad LSFA ↔ email-agent-kdd

Este documento registra la validación del puente entre la propuesta LSFA 0.2 y
la CLI de correo. La prueba es local, determinista y no conecta con servidores,
no descarga mensajes, no envía correo y no carga credenciales.

## Compatibilidad verificada

| Capacidad LSFA | Implementación de correo | Resultado |
| --- | --- | --- |
| Solicitud declarativa | `src/email/lsfa_bridge.py` | Compatible |
| Campos sensibles sin valores | `connect_email_request` y `send_email_request` | Compatible |
| Preflight antes de persistir | `imap_auth_and_smtp_auth` | Declarado |
| Riesgo alto para envío | `risk: high` | Compatible |
| Confirmación humana | `user_accept` / `pin` | Compatible |
| Confirmación de un solo uso | `single_use: true` | Compatible |
| Resultado sin secretos | Contrato LSFA del cliente | Obligatorio al ejecutar |
| Extracción de adjuntos | `extract_attachment_request` | Compatible con extensión LSFA |

## Límites actuales

- El puente declara solicitudes; no reemplaza al cliente LSFA que presenta el
  formulario ni al almacén seguro.
- La comprobación real de IMAP/SMTP ocurre únicamente durante el flujo de
  configuración del usuario y no forma parte de esta prueba estática.
- La extracción usa la extensión `specs/lsfa-attachments.md`; el CLI conserva
  su política de autorización, tipo, hash y presupuesto.

## Reproducir

Desde la raíz del proyecto:

```text
python -m pytest outputs/email-agent-kdd/tests/frozen_lsfa_integration.py -q
```

Si una futura modificación añade valores de credenciales, permite
confirmaciones reutilizables o cambia el riesgo del envío, la prueba debe fallar
y el cambio debe revisarse antes de publicarse.
