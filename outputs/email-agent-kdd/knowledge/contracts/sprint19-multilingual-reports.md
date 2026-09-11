---
type: KDD Contract
id: email-agent-sprint19-multilingual-reports
objective: Exportar diagnósticos legibles en español, inglés y portugués
status: frozen
---

- `doctor` acepta `--lang es|en|pt`.
- `doctor` acepta `--format json|text`.
- JSON conserva nombres estables para agentes y texto es legible para personas.
- Todos los formatos excluyen secretos, rutas completas y contenido de correo.
- La escritura sigue siendo local, atómica y no automática.
