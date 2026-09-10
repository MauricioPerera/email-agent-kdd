---
type: Architecture Decision
title: Arquitectura inicial del sistema de correo
description: Separación entre evidencia de correo, conocimiento OKF, índices y herramientas del agente.
status: draft
tags: [arquitectura, correo, agente, mvp]
---

# Componentes

- **CLI:** configuración guiada, sincronización, consulta, borradores y confirmación.
- **Adaptador de proveedor:** conexión real actual vía `env://` (credenciales en el entorno) con IMAP para lectura y SMTP para envío; devuelve mensajes normalizados y cursores. OAuth (Gmail) es fase futura, no implementada.
- **Ingestor:** valida MIME, calcula hashes, conserva la evidencia del mensaje y genera nodos OKF. De los adjuntos solo detecta y persiste metadatos (`name`, `mime_type`, `size`, `sha256`); los binarios y los `raw` del mensaje no llegan a la persistencia (ver `contracts/attachments-policy.md`).
- **Store:** SQLite para IDs, relaciones, estados y búsqueda FTS5.
- **Bundle OKF:** Markdown con frontmatter YAML y enlaces entre conceptos.
- **Capa agente:** herramientas pequeñas para buscar, leer, crear borradores y confirmar envíos.

# Flujo de envío

`solicitud del agente -> borrador pendiente -> revisión del usuario -> confirmación -> envío -> registro inmutable`

# Decisiones

La evidencia original no se modifica al reindexar. De los adjuntos solo persisten metadatos: nunca se almacenan ni exponen binarios, no se envían adjuntos ni se extrae texto de ellos; el acceso duradero al contenido (`retrieve_attachment`, con autorización explícita y antivirus) queda como fase futura. Los resúmenes y temas se regeneran sin sobrescribir el mensaje original. Los embeddings, si se incorporan, son un índice derivado y opcional.
