---
task: create_email_account
intent: registrar localmente una cuenta de correo como registro serializable sin conectar nada
target: src/email/account.py
signature: "def create_email_account(account_id: str, provider: str, email: str, credential_ref: str) -> dict"
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 80
  params_max: 5
tests: tests/frozen_create_account.py
deps_allowed: []
forbids: [eval, exec, subprocess, network_access, smtplib, socket, urllib, requests]
---

## Intent

Registrar localmente una cuenta de correo como un registro serializable y determinista (preparacion para OAuth/sincronizacion futura), sin contactar ningun proveedor. La funcion solo construye el objeto en memoria; jamas se conecta, guarda, envia credenciales ni escribe archivos.

## Interface

`def create_email_account(account_id: str, provider: str, email: str, credential_ref: str) -> dict`

- `account_id`: identificador local de la cuenta (str no vacio tras `strip`); se copia al registro sin alterar.
- `provider`: nombre del proveedor (str no vacio tras `strip`); puede traer espacios o mayusculas.
- `email`: direccion de correo cruda (str no vacia tras eliminar espacios); puede traer espacios o mayusculas.
- `credential_ref`: referencia opaca a la credencial (str no vacio tras `strip`); es texto que apunta a donde vive el secreto (por ejemplo `keyring://gmail/personal`), NUNCA el secreto mismo.
- Devuelve: `dict` serializable a JSON con las claves `account_id`, `provider`, `email`, `credential_ref`, `status`, en ese orden.
- Lanza: `ValueError` si alguno de los cuatro argumentos no es `str` o queda vacio tras su validacion.

Normalizacion (regla exacta, sin excepciones):

1. `provider` en el registro es `provider.strip().lower()` (minusculas, bordes recortados).
2. `email` en el registro es el texto en minusculas con TODOS los caracteres de espacio en blanco eliminados, no solo los de los bordes (ej. `"Ana @ Example.COM "` -> `"ana@example.com"`).
3. `account_id` y `credential_ref` se copian verbatim, sin normalizar.

`credential_ref` opaco (regla exacta): la funcion no lo interpreta, no lo abre, no lo resuelve y no lo valida en contenido; solo lo copia como texto en el registro. Nunca acepta, genera ni devuelve secretos.

`status` inicial (regla exacta): el registro siempre arranca con `status: "disconnected"`; no existe conexion, sesion ni token en este contrato.

## Invariants

- El registro devuelto siempre lleva `status: "disconnected"`; la funcion no lo cambia jamas.
- `provider` y `email` en el registro son exactamente los normalizados por la regla de la Interface; `email` no contiene ningun caracter de espacio en blanco.
- `account_id` y `credential_ref` aparecen en el registro verbatim, sin alterar.
- `credential_ref` es solo texto opaco: la funcion jamas lo interpreta, lo abre ni lo registra en logs, y el resultado nunca contiene secretos.
- El registro es determinista: misma entrada, mismo dict; sin reloj, sin aleatoriedad, sin marcas de tiempo.
- Todas las claves y valores del registro son `str`: el dict es serializable a JSON sin perdida.
- La funcion es pura respecto a la red y al disco: no se conecta, no escribe archivos, no abre sockets y no importa `smtplib`, `socket`, `urllib` ni `requests`.
- Una entrada invalida se rechaza con `ValueError` antes de construir el registro y no deja estado parcial.

## Examples

- Ejemplo frozen: entradas crudas con espacios y mayusculas se normalizan a minusculas, con `credential_ref` opaco copiado verbatim y `status: "disconnected"`.

```frozen-example
{
  "account_id": "personal",
  "provider": "gmail",
  "email": "ana@example.com",
  "credential_ref": "keyring://gmail/personal",
  "status": "disconnected"
}
```

```frozen-inputs
[
  "personal",
  "  Gmail  ",
  "  Ana @ Example.COM ",
  "keyring://gmail/personal"
]
```

Entrada del ejemplo: los cuatro argumentos del bloque `frozen-inputs`, en orden.

- Casos invalidos que lanzan `ValueError`:

```frozen-invalid-inputs
{"account_id": ["", "  ", 7, null, true], "provider": ["", "  ", "GMAIL\n", 7, null], "email": ["", "  ", " \t ", "ana@x.com\n", 7, null], "credential_ref": ["", "  ", 7, null, true]}
```

- `create_email_account(...)` dos veces con la misma entrada devuelve dicts iguales pero distintos objetos (`result is not result2`).
- Los cuatro argumentos de entrada quedan intactos tras la llamada: la creacion del registro no muta la entrada.

## Do / Don't

- Do: normalizar `provider` con `strip().lower()` y `email` a minusculas eliminando todos los espacios en blanco.
- Do: copiar `account_id` y `credential_ref` verbatim y devolver un dict con `status: "disconnected"`.
- Do: tratar `credential_ref` como referencia opaca: solo texto en el registro, jamas el secreto.
- Don't: conectarse a un proveedor, iniciar OAuth, sincronizar correo o usar `smtplib`, `socket`, `urllib`, `requests` o `subprocess`.
- Don't: escribir archivos, tocar la red o depender del reloj o del azar.
- Don't: validar el formato del `email` mas alla de la regla de espacios, interpretar `credential_ref`, loguear secretos o mutar los argumentos de entrada.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_create_account.py`. Son oracle independiente: no importan el target ni `src.email`. Verifican el frontmatter del contrato (budgets, deps, forbids), las 7 secciones, la frase `PARAR y reportar si`, el ejemplo frozen recomputando las reglas de normalizacion documentadas, el `status: "disconnected"`, el caracter opaco de `credential_ref` y los casos invalidos con `ValueError`.

## Constraints

Presupuestos: ciclomatica <= 20, anidamiento <= 4, lineas <= 80, parametros <= 5. Solo dependencias de `deps_allowed` (ninguna externa: stdlib minima, sin imports de terceros). PARAR y reportar si la regla de normalizacion de `provider` o `email` no puede implementarse tal como esta documentada, si la validacion requiere algo mas que comprobar tipo `str` y no-vacio, si `credential_ref` necesita interpretarse o transformarse para guardar el registro, si el estado inicial `disconnected` no basta para la preparacion OAuth futura, o si el resultado no es serializable a JSON sin perdida.