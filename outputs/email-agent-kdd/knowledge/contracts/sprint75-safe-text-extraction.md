---
type: KDD Contract
id: email-agent-sprint75-safe-text-extraction
objective: Extraer texto de adjuntos almacenados sin ejecutar contenido activo
status: frozen
---

- `attachment extract ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION` requiere autorización literal;
- solo procesa blobs `stored: true` con tipos UTF-8 de texto soportados;
- valida hash, tamaño y ausencia de contenido binario antes de escribir;
- no contacta IMAP, no modifica el nodo OKF y no envía correo;
- PDF, HTML, documentos ofimáticos y ejecutables quedan rechazados hasta contar con sandbox y antivirus;
- el destino es relativo y permanece bajo `ROOT`.
