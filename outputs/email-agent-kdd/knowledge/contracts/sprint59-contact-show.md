---
type: KDD Contract
id: email-agent-sprint59-contact-show
objective: Consultar un contacto exacto sin mutar la libreta
status: frozen
---

- `contact show ROOT EMAIL` devuelve un solo contacto;
- la comparación ignora espacios exteriores y mayúsculas del email;
- el nombre se devuelve desde la libreta, sin inferencia;
- contacto ausente devuelve error;
- contacto ausente no crea ni modifica `contacts.json`.
