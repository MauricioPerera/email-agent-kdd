---
type: KDD Contract
id: email-agent-sprint68-draft-show
objective: Mostrar un borrador antes de solicitar autorización de envío
status: frozen
---

- `draft show ROOT DRAFT_ID` es una operación de solo lectura;
- muestra el contenido exacto persistido del borrador para revisión del usuario;
- valida el identificador como un sha256 y no permite salir de `ROOT/drafts`;
- no resuelve cuentas, credenciales ni conexiones de red;
- no modifica el archivo del borrador ni cambia su estado;
- el agente debe presentar la vista previa antes de solicitar `CONFIRMAR ENVIO`.
- la salida usa una lista cerrada de campos y omite cualquier campo extra persistido.
