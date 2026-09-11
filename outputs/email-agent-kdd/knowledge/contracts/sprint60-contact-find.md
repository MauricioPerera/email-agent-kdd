---
type: KDD Contract
id: email-agent-sprint60-contact-find
objective: Encontrar candidatos de contacto sin mutar la libreta
status: frozen
---

- `contact find ROOT TEXT` busca por nombre o email;
- la búsqueda es insensible a mayúsculas;
- devuelve una línea JSON por candidato;
- texto vacío devuelve error de argumentos;
- encontrar candidatos no autoriza buscar, enviar o cambiar datos automáticamente.
