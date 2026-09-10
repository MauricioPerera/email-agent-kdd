---
type: Data Model
title: Modelo OKF para correo
description: Tipos y relaciones del conocimiento derivado de mensajes de correo.
status: draft
tags: [okf, mensajes, hilos, contactos, adjuntos]
---

# Tipos

- `Email Message`: mensaje individual, inmutable, con headers y cuerpo normalizado.
- `Email Thread`: conversación agregada con enlaces a sus mensajes.
- `Email Contact`: identidad consolidada por dirección de correo.
- `Email Attachment`: metadatos de referencia (`name`, `mime_type`, `size`, `sha256`); sin binario.
- `Email Topic`: agrupación derivada, siempre enlazada a mensajes fuente.

# Relaciones

- Un mensaje pertenece a un hilo.
- Un mensaje referencia sus contactos participantes.
- Un mensaje puede enlazar varios adjuntos.
- Un hilo puede enlazar temas derivados.
- Todo resumen o clasificación debe enlazar los mensajes que lo sustentan.

# Adjuntos

Según la decisión vigente de `contracts/attachments-policy.md`, en el MVP el binario NO se almacena en ningún lado: el nodo OKF conserva únicamente los metadatos `name`, `mime_type`, `size` y `sha256` (más el mensaje de origen). No se persisten ni exponen binarios, `raw` ni fragmentos decodificados. El `sha256` sirve como identidad del adjunto para deduplicación y referencia estable entre nodos. La extracción de texto de adjuntos y el acceso duradero al contenido (`retrieve_attachment`, con autorización y antivirus) son fase futura y no existen en el MVP.
