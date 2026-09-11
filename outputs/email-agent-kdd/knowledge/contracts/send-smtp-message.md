---
task: send_smtp_message
intent: enviar un correo ya confirmado por SMTP devolviendo un recibo serializable
target: src/email/smtp_send.py
signature: "def send_smtp_message(account: dict, config: dict, message: dict, connection_factory=None) -> dict"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 4
tests: tests/frozen_send_smtp.py
test_command: python -m pytest tests/frozen_send_smtp.py -q
deps_allowed: [smtplib, email, typing]
forbids: [eval, exec, subprocess, filesystem_write, print, logging]
---

## Intent

Enviar, y solo si el remitente confirmo explicitamente el envio, un correo por SMTP y devolver un recibo serializable de la entrega. La funcion valida toda la entrada antes de conectar, usa una fabrica de conexion inyectable para que las pruebas no toquen red, construye un `EmailMessage`, hace `login` y `send_message`, cierra la sesion en `finally` y jamas expone la password ni deja rastro en disco o logs.

## Interface

`def send_smtp_message(account: dict, config: dict, message: dict, connection_factory=None) -> dict`

- `account` (obligatorio): dict con `account_id` y `email`, ambos `str` no vacios.
- `config` (obligatorio): dict con `host`, `username` y `password`, todos `str` no vacios; claves opcionales `port` (`int` de `1` a `65535`, por defecto `587`, los `bool` se rechazan aunque Python los cuente como `int`) y `from_email` (`str` no vacio, por defecto `account["email"]`).
- `message` (obligatorio): dict con `confirmed` (`bool` que debe ser exactamente `True` por identidad `is True`), `to` (lista no vacia de `str` no vacios, usados tal cual y en orden, sin normalizar), `subject` (`str` no vacio) y `body` (`str` no vacio). Cualquier otra clave se ignora.
- `connection_factory` (opcional): callable que recibe `(host, port)` y devuelve un objeto conexion con `login`, `send_message` y `quit`. Si es `None`, la funcion selecciona la fabrica por defecto segun el puerto resuelto: con `port == 465` construye `smtplib.SMTP_SSL(host, port)` (TLS implicito); con cualquier otro puerto (`587` incluido) construye `smtplib.SMTP(host, port)`.
- Devuelve: `dict` de recibo serializable a JSON, con exactamente las claves `account_id`, `from_email`, `to` (copia de la lista), `subject` y `sent` (`True`), en ese orden. Sin password, sin el cuerpo y sin objetos no serializables.
- Lanza: `ValueError` ante cualquier entrada invalida, siempre antes de llamar a la fabrica; `RuntimeError` ante cualquier error de transporte.

## Invariants

- Confirmacion estricta: el envio solo procede si `message["confirmed"] is True`. Los valores `1`, `"true"`, `"yes"`, `None` o `False` NO confirman y se rechazan con `ValueError`: si no hay confirmacion exacta la funcion nunca ejecuta y nunca abre conexion.
- Validacion previa a toda conexion, en orden fijo: (1) `account` dict con `account_id` y `email` utiles, (2) `config` dict con `host`, `username` y `password` utiles, (3) `port` si esta presente dentro de `1..65535` y no es `bool`, (4) `from_email` si esta presente `str` no vacio, (5) `message` dict, (6) `confirmed is True`, (7) `to` lista no vacia de `str` no vacios, (8) `subject` `str` no vacio, (9) `body` `str` no vacio. Cualquier fallo lanza `ValueError` y la fabrica nunca se invoca.
- Construccion del mensaje: `email.message.EmailMessage()` con `From` = `from_email` resuelto, `To` = `", ".join(to)`, `Subject` = `subject` y `set_content(body)`. La funcion no altera cabeceras extra ni adjunta nada.
- Secuencia SMTP fija: `connection_factory(host, port)` -> `login(username, password)` -> `send_message(msg)`; `quit()` se ejecuta en un `finally`, tambien cuando la fabrica, el `login` o el `send_message` fallan a mitad del camino.
- Fabrica por defecto segun puerto (solo cuando `connection_factory is None`): puerto `465` -> `smtplib.SMTP_SSL` (TLS implicito); cualquier otro puerto -> `smtplib.SMTP`. Una fabrica inyectada se usa siempre tal cual, sin importar el puerto.
- Todo error de transporte (fabrica, `login`, `send_message`) se relanza como `RuntimeError` cuyo mensaje incluye `host` y `account_id` pero nunca la password (ni en claro ni codificada) y nunca el cuerpo del mensaje.
- Sin disco, sin logs, sin `print`, sin `logging` y sin dependencias externas: la unica red posible es la fabrica inyectada.
- La entrada no se muta: `account`, `config` y `message` quedan intactos tras la llamada.

## Examples

Ejemplo frozen de exito (fabrica inyectada): un solo intento de conexion, una sola entrega capturada por el fake, sesion cerrada y recibo exacto.

- `send_smtp_message({"account_id": "personal", "email": "yo@inbox.test"}, {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-1"}, {"confirmed": True, "to": ["ana@example.com"], "subject": "Hola", "body": "Cuerpo."}, fake_factory) -> {"account_id": "personal", "from_email": "yo@inbox.test", "to": ["ana@example.com"], "subject": "Hola", "sent": True}` con una sola entrega capturada por el fake y una sola conexion.
- `send_smtp_message(account_valido, {"host": "smtp.corp.test", "username": "u", "password": "frozen-secret-2", "port": 465, "from_email": "no-reply@corp.test"}, message_confirmado, fake_factory) -> recibo con `from_email: "no-reply@corp.test"` y `sent: True`, conexion en el puerto `465`.
- `send_smtp_message(account_valido, config_valido, {"to": ["ana@example.com"], "subject": "Hola", "body": "Texto."}, fake_factory) -> ValueError` (falta `confirmed`, la fabrica nunca se invoca: `factory_calls == 0`).
- `send_smtp_message(account_valido, config_valido, {"confirmed": 1, "to": ["ana@example.com"], "subject": "Hola", "body": "Texto."}, fake_factory) -> ValueError` (`1` no es `True` por identidad).
- Si `send_message` lanza un error de transporte con `confirmed is True`, el resultado es `RuntimeError` (mensaje con `host` y `account_id`, sin la password ni el cuerpo) y `quit()` se ejecuto igualmente en el `finally`.

```frozen-cases
[
  {
    "name": "success_default_port_and_from",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-1"},
    "message": {"confirmed": true, "to": ["ana@example.com", "pepe@corp.test"], "subject": "Hola", "body": "Cuerpo de prueba."},
    "send_error": null,
    "expected": {
      "error": null,
      "factory_calls": 1,
      "port": 587,
      "from_email": "yo@inbox.test",
      "to_header": "ana@example.com, pepe@corp.test",
      "deliveries": 1,
      "quit_calls": 1,
      "receipt": {"account_id": "personal", "from_email": "yo@inbox.test", "to": ["ana@example.com", "pepe@corp.test"], "subject": "Hola", "sent": true},
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "success_explicit_port_and_from",
    "account": {"account_id": "work", "email": "trabajo@corp.test"},
    "config": {"host": "smtp.corp.test", "username": "u", "password": "frozen-secret-2", "port": 465, "from_email": "no-reply@corp.test"},
    "message": {"confirmed": true, "to": ["ana@example.com"], "subject": "Asunto", "body": "Texto."},
    "send_error": null,
    "expected": {
      "error": null,
      "factory_calls": 1,
      "port": 465,
      "from_email": "no-reply@corp.test",
      "to_header": "ana@example.com",
      "deliveries": 1,
      "quit_calls": 1,
      "receipt": {"account_id": "work", "from_email": "no-reply@corp.test", "to": ["ana@example.com"], "subject": "Asunto", "sent": true},
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "missing_confirmation_no_connection",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-3"},
    "message": {"confirmed": 1, "to": ["ana@example.com"], "subject": "Hola", "body": "Cuerpo de prueba."},
    "send_error": null,
    "expected": {
      "error": "ValueError",
      "factory_calls": 0,
      "port": null,
      "from_email": null,
      "to_header": null,
      "deliveries": 0,
      "quit_calls": 0,
      "receipt": null,
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "unconfirmed_flag_false_no_connection",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-4"},
    "message": {"confirmed": false, "to": ["ana@example.com"], "subject": "Hola", "body": "Cuerpo de prueba."},
    "send_error": null,
    "expected": {
      "error": "ValueError",
      "factory_calls": 0,
      "port": null,
      "from_email": null,
      "to_header": null,
      "deliveries": 0,
      "quit_calls": 0,
      "receipt": null,
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "invalid_subject_no_connection",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-5"},
    "message": {"confirmed": true, "to": ["ana@example.com"], "subject": "", "body": "Texto."},
    "send_error": null,
    "expected": {
      "error": "ValueError",
      "factory_calls": 0,
      "port": null,
      "from_email": null,
      "to_header": null,
      "deliveries": 0,
      "quit_calls": 0,
      "receipt": null,
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "invalid_account_no_connection",
    "account": {"account_id": "personal"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-6"},
    "message": {"confirmed": true, "to": ["ana@example.com"], "subject": "Hola", "body": "Texto."},
    "send_error": null,
    "expected": {
      "error": "ValueError",
      "factory_calls": 0,
      "port": null,
      "from_email": null,
      "to_header": null,
      "deliveries": 0,
      "quit_calls": 0,
      "receipt": null,
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "port_out_of_range_no_connection",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-7", "port": 70000},
    "message": {"confirmed": true, "to": ["ana@example.com"], "subject": "Hola", "body": "Texto."},
    "send_error": null,
    "expected": {
      "error": "ValueError",
      "factory_calls": 0,
      "port": null,
      "from_email": null,
      "to_header": null,
      "deliveries": 0,
      "quit_calls": 0,
      "receipt": null,
      "message_contains": null,
      "message_not_contains": null
    }
  },
  {
    "name": "transport_error_wrapped_without_password",
    "account": {"account_id": "personal", "email": "yo@inbox.test"},
    "config": {"host": "smtp.example.test", "username": "usuario", "password": "frozen-secret-8"},
    "message": {"confirmed": true, "to": ["ana@example.com"], "subject": "Hola", "body": "Texto."},
    "send_error": "smtplib.SMTPAuthenticationError: fallo de autenticacion",
    "expected": {
      "error": "RuntimeError",
      "factory_calls": 1,
      "port": 587,
      "from_email": "yo@inbox.test",
      "to_header": "ana@example.com",
      "deliveries": 0,
      "quit_calls": 1,
      "receipt": null,
      "message_contains": ["smtp.example.test", "personal"],
      "message_not_contains": ["frozen-secret-8", "Texto."]
    }
  }
]
```

## Do / Don't

- Do: validar toda la entrada (incluida la confirmacion exacta `is True`) antes de llamar a la fabrica.
- Do: aceptar la fabrica inyectada para toda conexion, de modo que las pruebas no toquen red.
- Do: con fabrica por defecto, elegir `smtplib.SMTP_SSL` solo para puerto `465` y `smtplib.SMTP` para los demas.
- Do: cerrar la sesion con `quit()` en un `finally` y devolver un recibo JSON-serializable sin password ni cuerpo.
- Don't: conectar, loguear o enviar sin `confirmed is True`.
- Don't: escribir archivos, emitir logs, usar `print`/`logging` ni dependencias externas.
- Don't: incluir la password (en claro o codificada) ni el cuerpo en errores, recibos o cualquier salida.

## Tests

Las propiedades y casos congelados estan en `tests/frozen_send_smtp.py`. Son oracle independiente: no importan el target ni `src.email`; no abren sockets ni escriben disco. Recomputan con un modelo de referencia propio y un fake SMTP las reglas documentadas (orden de validacion, confirmacion estricta `is True`, valores por defecto de `port`/`from_email`, secuencia factory/login/send_message con `quit` en `finally`, envoltura de errores en `RuntimeError` sin password ni cuerpo, recibo de claves exactas) y las contrastan con los casos congelados. La prueba valida ademas que sin confirmacion no se abre ninguna conexion (`factory_calls == 0`) y que el fake captura exactamente una entrega en el caso de exito. La seleccion de la fabrica por defecto segun puerto (`smtplib.SMTP_SSL` solo para `465`; `smtplib.SMTP` para los demas, incluido `587`) se cubre con la prueba de regresion `tests/frozen_smtp_ssl_port.py`, que sustituye `smtplib.SMTP` y `smtplib.SMTP_SSL` por fakes y por tanto no abre sockets reales.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 4. Solo dependencias de `deps_allowed` (`smtplib`, `email`, `typing`); ninguna externa. La funcion no escribe disco, no emite logs y su unica red es la fabrica inyectada (por defecto `smtplib.SMTP`). El recibo es exactamente `{account_id, from_email, to, subject, sent}` y no contiene password ni cuerpo. PARAR y reportar si la validacion no puede completarse antes de abrir conexion, si la confirmacion no puede exigirse por identidad `is True` (aceptando `1` u otras verdades no booleanas), si `quit()` no puede garantizarse en `finally` para los tres puntos de fallo, si un error de transporte no puede envolverse en `RuntimeError` sin exponer la password o el cuerpo, si el recibo requiere claves distintas de las documentadas, si se necesita dependencia externa, `subprocess`, escritura en disco, logs o red fuera de la fabrica inyectada, o si `port` requiere aceptar valores fuera de `1..65535` o no enteros.