---
task: email_provider_protocol
intent: definir la frontera estructural de un proveedor de correo como Protocol de stdlib sin implementacion de red
target: src/email/provider.py
signature: "class EmailProvider(Protocol)"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_email_provider.py
deps_allowed: [typing]
forbids: [eval, exec, subprocess, network_access, smtplib, socket, urllib, requests, imaplib, poplib]
---

## Intent

Definir la frontera de proveedor de correo como una interfaz MINIMA y estructural (Protocol de `typing`, solo stdlib): declara QUE debe saber hacer un adaptador de proveedor, nunca COMO lo hace. La interfaz no conecta, no envia, no abre credenciales y no escribe disco; existe para que el CLI agent-ready pueda leer y escribir correo contra cualquier adaptador concreto con una orden de envio YA confirmada.

## Interface

`class EmailProvider(Protocol)` (decorada con `@runtime_checkable` para que un adaptador concreto pueda verificarse por estructura con `isinstance`).

- `list_messages(account: dict, query: str = "") -> list[dict]`
- `send_message(account: dict, message: dict) -> dict`

- `account`: dict serializable a JSON, el registro de cuenta de `create_email_account` (claves `account_id`, `provider`, `email`, `credential_ref`, `status`). La interfaz NO lo interpreta: `credential_ref` sigue siendo texto opaco que apunta al secreto, NUNCA el secreto mismo, y la interfaz no lo abre, no lo resuelve ni lo loguea.
- `query` (solo `list_messages`): `str`, vacio por defecto; vacio significa listar los mensajes recientes. La interpretacion exacta del dialecto de busqueda es del adaptador concreto; la interfaz no impone sintaxis.
- `message` (solo `send_message`): dict serializable a JSON que representa UNA orden de envio ya confirmada. Debe incluir al menos `confirmed: true`, destinatario(s) bajo `to` (str o lista de str), `subject` (str) y `body` (str). Ejemplo frozen de orden:

```frozen-message
{"confirmed": true, "to": ["ana@example.com"], "subject": "hola", "body": "texto del borrador", "draft_id": "draft-1"}
```

```frozen-account
{"account_id": "personal", "provider": "gmail", "email": "ana@example.com", "credential_ref": "keyring://gmail/personal", "status": "disconnected"}
```

- `list_messages` devuelve una `list[dict]` donde cada dict es un mensaje serializable a JSON.
- `send_message` devuelve un dict serializable a JSON: el RECIBO del envio que el adaptador concreto produce. La interfaz no define las claves del recibo, solo que sea serializable.
- La interfaz NO valida en tiempo de ejecucion (Protocol estructural, cuerpos vacios): las reglas de esta seccion son el contrato que el oraculo congela y que cada adaptador concreto debe cumplir.

## Invariants

- `EmailProvider` es un Protocol estructural: no hay clase base concreta, no hay estado ni implementacion; los cuerpos de los metodos solo llevan docstring.
- La interfaz expone EXACTAMENTE los dos metodos publicos `list_messages` y `send_message`; no existe ningun metodo que envie sin confirmacion.
- `send_message` solo recibe una orden YA confirmada (`message["confirmed"] is True`): el adaptador concreto recibira la decision confirmada por la capa de confirmacion; esta interfaz NO ofrece ningun camino para saltarse la confirmacion y los adaptadores deben rechazar una orden sin `confirmed: true` con `ValueError`.
- `account` y `message` son dicts serializables a JSON sin perdida; `credential_ref` permanece opaco dentro de `account`.
- La interfaz es pura respecto a la red y al disco: no se conecta, no envia, no escribe archivos, no abre sockets y no importa `smtplib`, `socket`, `urllib`, `requests`, `imaplib` ni `poplib`.
- Los unicos imports permitidos son stdlib (`typing`); ninguna dependencia externa, ningun paquete de terceros.
- La interfaz no depende del reloj ni del azar y no muta sus argumentos de entrada.

## Examples

- Orden de envio frozen (`frozen-message`) y registro de cuenta frozen (`frozen-account`) usados como entrada tipica: el adaptador recibe la cuenta como dict opaco y la orden con `confirmed: true`.
- `list_messages(account, "")` devuelve la lista de mensajes recientes; `list_messages(account, "desde:ana@example.com")` delega el filtro al adaptador.
- Un adaptador concreto cumple la interfaz por estructura (sin heredar) si define ambos metodos con las mismas firmas: `isinstance(adapter, EmailProvider)` es `True` por `runtime_checkable`.

## Do / Don't

- Do: mantener la interfaz minima: dos metodos, dicts serializables, cero implementacion de red.
- Do: documentar que `send_message` recibe una orden ya confirmada y devolver el recibo como dict serializable.
- Do: tratar `account` como registro opaco serializable y `credential_ref` como referencia al secreto, nunca el secreto.
- Don't: implementar SMTP/IMAP, OAuth, sesiones, reintentos ni cache en esta interfaz; eso es de los adaptadores.
- Don't: usar `smtplib`, `socket`, `urllib`, `requests`, `imaplib`, `poplib` o `subprocess`; no conectar ni escribir disco.
- Don't: anadir metodos que permitan enviar sin confirmacion, validar credenciales en la interfaz o loguear secretos.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_email_provider.py`. Son oracle independiente: NO importan el target ni `src.email`. Verifican el frontmatter del contrato (budgets, deps, forbids), las 7 secciones, la frase `PARAR y reportar si`, la estructura del modulo `src/email/provider.py` por AST sin importarlo (Protocol + `runtime_checkable`, firmas exactas, imports solo de `typing`), que los cuerpos no ejecutan nada (sin print, open ni llamadas), que los dicts frozen son serializables a JSON, que la orden lleva `confirmed: true` y que la interfaz no puede saltarse la confirmacion.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed` (`typing`); ninguna externa. PARAR y reportar si la interfaz necesita mas de los dos metodos documentados, si `list_messages` o `send_message` requieren otra firma o otro tipo de retorno, si el dict `message` necesita claves distintas de las documentadas (o no basta `confirmed: true` para representar la orden confirmada), si la interfaz no puede expresarse como Protocol de stdlib sin implementar red, o si serializar `account`/`message`/recibo a JSON no es posible sin perdida.