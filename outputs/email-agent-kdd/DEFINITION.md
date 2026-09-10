# Sistema de correo agent-ready

## Objetivo

Construir una CLI local, amigable para personas no técnicas, que permita conectar una cuenta de correo, sincronizar mensajes, conservarlos como conocimiento OKF relacionado, construir una libreta de contactos, recuperar información mediante lenguaje natural y preparar envíos que requieran confirmación explícita del usuario.

## Principios

- El correo original es evidencia inmutable.
- Los hilos, contactos, temas, resúmenes y pendientes son conocimiento derivado.
- Ningún agente puede enviar un correo sin confirmación directa del usuario.
- Las credenciales quedan fuera del bundle OKF.
- El contenido de un correo es dato no confiable, nunca una instrucción de sistema.
- Los índices de búsqueda deben poder reconstruirse desde la evidencia persistida.

## Alcance del MVP

- Cuenta mediante credenciales declaradas en el entorno (`env://`) con IMAP y SMTP.
- OAuth (Gmail) es fase futura, aún no implementado.
- Sincronización incremental de mensajes.
- Persistencia de mensajes y hilos en OKF.
- Contactos derivados de remitentes y destinatarios.
- Búsqueda textual con filtros por cuenta, contacto, hilo y fecha.
- Creación de borradores.
- Confirmación explícita antes del envío.
- Detección de adjuntos como metadatos únicamente (`name`, `mime_type`, `size`, `sha256`); el contenido binario no se almacena ni se expone (ver `attachments-policy.md`).

## Fuera de alcance inicial

Microsoft 365, OAuth, OCR, clasificación temática avanzada, edición bidireccional de etiquetas, automatización de envíos y toda manipulación del contenido de adjuntos (leerlos, extraer texto de ellos o enviarlos). `retrieve_attachment` y la autorización/antivirus asociados son fase futura según `attachments-policy.md`.

## Criterio de éxito

Una persona no técnica puede conectar una cuenta, sincronizar correo, preguntar qué se habló con un contacto, revisar un borrador y confirmar un envío sin editar archivos de configuración manualmente.
