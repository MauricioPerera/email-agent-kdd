---
task: discover_mail_servers
intent: descubrir los servidores de correo IMAP/SMTP de un dominio propio desde el correo del usuario
target: src/email/discover_mail_servers.py
signature: "def discover_mail_servers(email: str, resolver=None) -> dict"
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 50
  params_max: 2
test_command: "python -m pytest outputs/email-agent-kdd/tests/frozen_discover_mail_servers.py -q"
tests: tests/frozen_discover_mail_servers.py
deps_allowed: []
forbids: [eval, exec, subprocess, print, open, logging, keyring, getpass, smtplib, imaplib, urllib, requests, environ]
---

## Intent

Descubrir de forma determinista los servidores de correo de un dominio propio: `discover_mail_servers(email, resolver=None)` valida la direccion cruda, deriva el dominio (minusculas, sin espacios) y devuelve SOLO `{"imap_host": str, "imap_port": int, "smtp_host": str, "smtp_port": int}`. La funcion JAMAS recibe ni maneja contrasenas ni secretos: el usuario del formulario solo escribe su correo. Un `resolver` inyectable define TODO el acceso a DNS en pruebas; con resolver inyectado la funcion JAMAS abre red. Si ni los registros del resolver, ni el mapa de proveedores conocidos, ni los candidatos del dominio confirman IMAP y SMTP completos, la funcion PARAR con `ValueError` claro para que la UI pida los datos avanzados sin tecnicismos.

## Interface

`def discover_mail_servers(email: str, resolver=None) -> dict`

- `email`: direccion cruda (`str` no vacia tras `strip`). Reglas EXACTAS: exactamente un `@`; local y dominio no vacios; dominio cumple `^[A-Za-z0-9._-]+$`, sin punto inicial/final ni `..`, longitud <= 253; el correo completo <= 254. El dominio se normaliza a minusculas. Entrada invalida: `ValueError` generico ANTES de cualquier consulta.
- `resolver`: protocolo del resolvor inyectable: un callable `resolver(name: str, rtype: str) -> list`. Devuelve una `list` de `str` (una entrada por registro) o `[]`/vacia cuando el registro NO existe; JAMAS lanza por "no encontrado". Registros SRV con formato `"<prioridad> <peso> <puerto> <objetivo>"`. Cualquier otra excepcion del resolver se PROPAGA tal cual. `resolver=None` usa el backend real.
- Devuelve: `dict` con EXACTAMENTE cuatro claves: `imap_host`, `imap_port`, `smtp_host`, `smtp_port`; puertos `int` en 1..65535; hosts en minusculas.
- Lanza: `ValueError` generico por correo invalido; `ValueError` generico `PARAR` por descubrimiento incompleto (mensajes genericos, sin detalles del resolver ni del DNS).

Orden EXACTO de descubrimiento (por flujo, IMAP y SMTP se resuelven INDEPENDIENTE; cada par `(name, rtype)` se consulta COMO MAXIMO una vez, en este orden fijo):

1. SRV seguro del resolver (solo si resolver no es None):
   - IMAP: `_imaps._tcp.<dominio>` (TLS implicito). SMTP: `_submissions._tcp.<dominio>` y, si no hay, `_submission._tcp.<dominio>` (submission).
   - De los registros devueltos se elige el de MENOR prioridad; empate: el PRIMERO en el orden devuelto. Registro malformado (campos de mas o de menos, prioridad/puerto no enteros, puerto fuera de 1..65535, objetivo vacio o `.`) se IGNORA sin error. Se recorta el punto final del objetivo y se valida como host; host invalido: se IGNORA el registro.
   - JAMAS se consultan `_imap._tcp` ni puertos inseguros (143, 25): la existencia DNS sin configuracion segura NO es soporte.
2. Mapa de proveedores conocidos (sin resolver, solo coincidencia EXACTA del dominio normalizado):
   - `gmail.com`, `googlemail.com` -> `imap.gmail.com:993` / `smtp.gmail.com:587`.
   - `outlook.com`, `hotmail.com`, `live.com`, `msn.com` -> `outlook.office365.com:993` / `smtp.office365.com:587`.
3. Candidatos comunes del dominio propio, SOLO si el resolver los confirma (`resolver(host, "A")` NO vacio; con `resolver=None` el backend real usa `socket.getaddrinfo` exclusivamente para esta confirmacion):
   - IMAP: `imap.<dominio>` y luego `mail.<dominio>`; puerto 993.
   - SMTP: `smtp.<dominio>` y luego `mail.<dominio>`; puerto 587.

Fallo claro: si IMAP o SMTP quedan sin confirmar -> `ValueError` generico de descubrimiento incompleto; JAMAS se devuelve parcial ni se adivina por heuristica silenciosa.

### Integracion con el formulario local

- El formulario solo recolecta el correo; `discover_mail_servers` deriva el dominio y devuelve hosts/puertos para precargar el formulario avanzado. Sin contrasenas, sin secretos, sin tokens en ningun paso.
- `ValueError` de descubrimiento incompleto: la UI lo traduce a "No pudimos detectar los servidores automaticamente; introduce los datos avanzados" y pide host/puerto manual. `resolver=None` permite discovery real en el proceso del formulario, solo con DNS/socket, JAMAS credenciales.
- La confirmacion significa que el dominio PUBLICA la configuracion/registro: el soporte real del protocolo se verifica DESPUES en la conexion de la cuenta, no aqui. La funcion jamas lo afirme de mas.

## Invariants

- El retorno tiene EXACTAMENTE las claves `imap_host`, `imap_port`, `smtp_host`, `smtp_port`: nunca claves extra, nunca parciales, nunca datos de credenciales.
- Con resolver inyectado la funcion JAMAS abre red: toda consulta pasa por el resolver; sin resolver, la unica red es la confirmacion de candidatos con `socket.getaddrinfo`, solo discovery, jamas conecta a un servidor de correo ni envia datos.
- Determinista: mismo email y mismo resolver -> mismo resultado y las MISMAS consultas en el MISMO orden; cada `(name, rtype)` como maximo una llamada; sin heuristica silenciosa ni azar.
- Existencia DNS no es soporte: solo se aceptan SRV de servicios seguros (`_imaps`, `_submissions`, `_submission`), candidatos confirmados por el resolver y el mapa conocido; todo lo demas PARAR.
- Validacion del email ANTES de la primera consulta; hosts y puertos del resultado siempre validados; jamas se derivan hosts de caracteres fuera de `[A-Za-z0-9._-]`.
- Sin impresion, sin archivos, sin logs, sin `subprocess`, sin librerias de terceros, sin UI; no muta los argumentos de entrada.
- Errores genericos: los mensajes no contienen detalles del resolver, del DNS ni de la red.

## Examples

- Ejemplo frozen: sobre el dominio conocido de Gmail, la llamada con los valores del bloque `frozen-inputs` devuelve exactamente el bloque `frozen-example`.

```frozen-inputs
{
  "email": "  Ana.Gomez@GMAIL.COM  "
}
```

```frozen-example
{"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}
```

- Entrada del ejemplo: `email` con espacios y mayusculas; el dominio se normaliza a `gmail.com` y coincide con el mapa conocido.
- Dominio propio `usuario@midominio.com` con un resolver falso: SRV vacios, `imap.midominio.com` y `smtp.midominio.com` confirmados por `A` -> `{"imap_host": "imap.midominio.com", "imap_port": 993, "smtp_host": "smtp.midominio.com", "smtp_port": 587}`.
- Fallback `mail.<dominio>`: dominio propio donde `imap.<dominio>` NO responde pero `mail.<dominio>` si -> IMAP es `mail.<dominio>:993`; el orden de candidatos es fijo.
- Prioridad: dominio Gmail con un resolver que publica `_imaps._tcp.gmail.com` apuntando a otro host/puerto -> GANA el SRV sobre el mapa conocido.
- Confirmacion incompleta: dominio propio donde NINGUN candidato confirma (resolver devuelve `[]` en todo) -> `ValueError` generico de descubrimiento incompleto, jamas retorno parcial.
- Correo invalido (`""`, `"   "`, `None`, `7`, `b"x"`, `"sin-arroba"`, `"a@@b.com"`, `"a@ b.com"`, `"a@.com"`, `"a@com."`, `"a@com..com"`, `"@x.com"`, `"x@"`) -> `ValueError` generico ANTES de la primera consulta; el resolver NO recibe ninguna llamada.
- Determinismo: dos llamadas identicas devuelven diccionarios iguales (y no el mismo objeto) y dejan en el resolver falso exactamente la misma secuencia de consultas, sin duplicados de `(name, rtype)`.

## Do / Don't

- Do: validar el correo primero, derivar el dominio y recorrer el orden fijo SRV seguro -> mapa conocido -> candidatos confirmados.
- Do: devolver solo las 4 claves con puertos `int` y hosts validados en minusculas, y PARAR con `ValueError` generico cuando algo no se confirma.
- Do: usar el resolver inyectado para TODO en pruebas y `socket.getaddrinfo` solo para confirmar candidatos cuando `resolver=None`.
- Don't: confundir existencia DNS con soporte de protocolo, aceptar `_imap._tcp`/puertos inseguros ni devolver un resultado parcial adivinado.
- Don't: recibir, tocar o inferir credenciales; imprimir, escribir archivos, loguear o usar `subprocess`; abrir red con resolver inyectado.
- Don't: mutar los argumentos de entrada ni depender de librerias de terceros.

## Tests

Las propiedades y ejemplos congelados estan en `tests/frozen_discover_mail_servers.py`. Son oracle independiente: NO importan `src.email` ni el target y JAMAS hacen red ni consultan DNS real; el resolver FALSO en memoria es OBLIGATORIO en todos los casos dinamicos. Verifican la estructura del contrato (frontmatter con presupuestos y `params_max: 2`, 7 secciones, regla `PARAR y reportar si`, protocolo del resolver, SRV `_imaps._tcp`/`_submissions._tcp`/`_submission._tcp`, mapa conocido Gmail/Outlook, candidatos `imap.`/`smtp.`/`mail.`, `getaddrinfo`, prohibicion de fallback inseguro) y ejercitan un modelo de referencia reimplementado en el propio test con las reglas documentadas: ejemplo frozen de Gmail, dominio propio con candidatos confirmados, fallback `mail.<dominio>`, prioridad del SRV sobre el mapa conocido, confirmacion incompleta PARANDO, correos invalidos sin ninguna consulta, determinismo con la misma secuencia de consultas y sin duplicados, puertos/hosts validados y ausencia de canales de escape en el modelo. Para el caso `resolver=None` el modelo del oracle NO simula red: solo verifica que el contrato documenta la regla del backend real.

## Constraints

Presupuestos por funcion: ciclomatica <= 12, anidamiento <= 3, lineas <= 50, parametros <= 2. Solo dependencias de `deps_allowed` (ninguna externa ni de terceros); los unicos usos de red permitidos son el resolver inyectado (protocolo `resolver(name, rtype) -> list`) y, con `resolver=None`, `socket.getaddrinfo` EXCLUSIVAMENTE para confirmar candidatos `imap.<dominio>`/`mail.<dominio>`/`smtp.<dominio>`; JAMAS se conecta a un servidor de correo, se envian credenciales o se tocan secretos (la funcion no los recibe). La funcion jamas imprime, escribe archivos, loguea ni ejecuta procesos; no usa `smtplib`, `imaplib`, `urllib`, `requests` ni `subprocess`. PARAR y reportar si el orden fijo SRV seguro -> mapa conocido -> candidatos confirmados no basta para cubrir el caso del formulario, si se necesitara aceptar `_imap._tcp` o puertos inseguros (143, 25) para no PARAR, si el retorno necesitara claves extra o parciales, si la confirmacion de un candidato no pudiera hacerse con el resolver inyectado o con `socket.getaddrinfo` sin enviar credenciales, si se necesitara una heuristica silenciosa insegura en lugar del `ValueError` generico de descubrimiento incompleto, si los mensajes de error no pudieran ser genericos, si se necesitara red distinta de la confirmacion de candidatos, o si la validacion del correo antes de la primera consulta no pudiera garantizarse.