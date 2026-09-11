---
type: KDD Contract
id: email-agent-sprint77-pdf-worker
objective: Extraer texto PDF en un proceso aislado y acotado
status: frozen
---

- el gate antivirus debe devolver `clean` antes de lanzar el worker;
- el worker recibe bytes por stdin y no usa red ni archivos temporales;
- se rechazan PDF cifrados, corruptos, mayores de 25 MiB o con más de 100 páginas;
- la salida está limitada a 4 MiB y el proceso a 15 segundos;
- solo se escribe el resultado después de validar su JSON y tamaño;
- el nodo OKF no se modifica y el resultado conserva el hash del adjunto;
- HTML y documentos ofimáticos siguen rechazados.
