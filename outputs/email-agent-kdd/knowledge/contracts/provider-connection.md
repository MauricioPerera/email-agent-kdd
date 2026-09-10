---
kind: knowledge-contract
name: provider-connection
status: propuesta
language: es
owner: email-agent-kdd
created: 2026-09-10
target: connect_provider
signature: "def connect_provider(provider: str, account_hint: dict, interactive: bool = True) -> dict"
scope: documentacion-futura
---

## Intent

Definir la interfaz futura `connect_provider(provider: str, account_hint: dict, interactive: bool = True) -> dict` que conecta una cuenta de correo (Gmail/Outlook) y devuelve una **cuenta pública sin secretos** compatible con `account_store`, documentando el estado real de hoy (IMAP/SMTP con `credential_ref` tipo `env://NOMBRE`, sin OAuth real ni almacenamiento de refresh tokens) y el camino futuro a OAuth (no implementado en este contrato).

## Interface

### Firma (futura)

```python
def connect_provider(provider: str, account_hint: dict, interactive: bool = True) -> dict:
    """Conecta una cuenta de correo y devuelve una cuenta pública sin secretos."""
```

### Parámetros

| Parámetro | Tipo | Semántica |
|---|---|---|
| `provider` | `str` | Proveedor objetivo. Valores válidos hoy: `"gmail"`, `"outlook"`. Cualquier otro valor es un error de dominio. |
| `account_hint` | `dict` | Datos que el usuario ya aporta: al menos `email`, y una referencia de credencial **por nombre**, p. ej. `credential_ref: "env://GMAIL_APP_PASSWORD"`. NUNCA la contraseña en claro. |
| `interactive` | `bool = True` | Si `True`, la función puede solicitar datos al usuario de forma interactiva (sin jamás pedir/imprimir contraseñas). Si `False`, debe fallar limpio en vez de bloquear. |

### Valor de retorno

Un `dict` con forma de cuenta pública, persistible directamente en `account_store`:

```python
{
    "provider": "gmail",
    "email": "usuario@gmail.com",
    "credential_ref": "env://GMAIL_APP_PASSWORD",
    "protocol": {"imap": "imap.gmail.com:993", "smtp": "smtp.gmail.com:587"},
    "connected": True,
    "auth_mode": "env-credential",   # "oauth" SOLO cuando OAuth exista de verdad
}
```

Garantía: el dict retornado **no contiene** contraseñas, tokens, refresh tokens ni ningún valor materializado del entorno; solo referencias simbólicas (`env://NOMBRE`).

### Estado real (implementado hoy)

- **Gmail y Outlook** vía **IMAP** (lectura) y **SMTP** (envío).
- Credenciales resueltas por referencia `env://NOMBRE` leída del entorno en el momento de uso; **no** hay OAuth real, **no** se almacenan refresh tokens, **no** hay callback local ni state/PKCE.
- Cualquier referencia a "OAuth" en este contrato es **diseño futuro**, no capacidad existente.

### OAuth (futuro — NO implementado, NO implementar en este contrato)

Cuando exista, deberá cumplir, sin afirmar que ya existe:

1. Autorización **visible y explícita** del usuario (consentimiento en pantalla del proveedor, nunca implícita ni por headless por defecto).
2. `state` anti-CSRF y **PKCE** (S256) en el flujo de autorización.
3. **Callback local** en `127.0.0.1` con puerto efímero, validación estricta de `redirect_uri`, y cierre inmediato tras recibir el código.
4. Tokens (access y refresh) **cifrados en reposo** y almacenados **fuera de OKF** (fuera del almacén de cuentas públicas), con archivo/almacén separado y permisos restrictivos.
5. **Scopes mínimos**: solo lectura/IMAP o envío/SMTP según el uso declarado; nunca `mail` completo ni scopes de todo el Drive si no se usan.
6. **Revocación**: comando/documentado para revocar el token en el proveedor y borrar el almacén local de tokens.
7. `auth_mode` pasa a `"oauth"` solo cuando los puntos 1–6 estén implementados y probados.

## Invariants

1. **Sin secretos en el resultado**: `connect_provider` nunca retorna, imprime, loguea ni persiste contraseñas, tokens o refresh tokens. Solo referencias `env://NOMBRE`.
2. **La CLI sigue con referencias de entorno**: hoy ninguna ruta de la CLI debe pedir, imprimir o persistir credenciales en claro; el cambio a OAuth no puede introducir ese comportamiento como efecto secundario.
3. **Compatibilidad con `account_store`**: el dict retornado es persistible tal cual en `account_store` y no requiere campos secretos para ser válido.
4. **`account_hint` no mutado**: la función no modifica el dict de entrada.
5. **`interactive=False` no bloquea**: sin interacción disponible y faltando datos, retorna error estructurado (ver abajo), nunca se queda esperando entrada.
6. **OAuth declarado ≠ OAuth existente**: mientras no exista, `auth_mode` es `"env-credential"` y ningún código de cliente puede asumir tokens de proveedor.
7. **Tokens fuera de OKF** (futuro): si OAuth llega, los tokens cifrados viven en su propio almacén, jamás dentro del archivo/colección de cuentas públicas.

## Examples

### Conexión válida con credencial de entorno (hoy)

```python
cuenta = connect_provider(
    "gmail",
    {"email": "yo@gmail.com", "credential_ref": "env://GMAIL_APP_PASSWORD"},
    interactive=False,
)
assert cuenta["provider"] == "gmail"
assert cuenta["credential_ref"] == "env://GMAIL_APP_PASSWORD"
assert "password" not in cuenta and "token" not in cuenta
assert cuenta["auth_mode"] == "env-credential"
# luego: account_store.save(cuenta)  ← persistible sin cambios
```

### `interactive=False` sin credencial disponible → error limpio

```python
try:
    connect_provider("outlook", {"email": "yo@outlook.com"}, interactive=False)
except ProviderConnectionError as e:
    # e.code == "missing_credential_ref": no bloquea, no pide nada, no adivina
    ...
```

### Proveedor no soportado

```python
try:
    connect_provider("proton", {"email": "yo@proton.me"}, interactive=False)
except ProviderConnectionError as e:
    assert e.code == "unsupported_provider"
```

### (Futuro, no hoy) OAuth

```python
# NO VÁLIDO HOY. Documenta la forma objetivo:
# cuenta = connect_provider("gmail", {"email": "yo@gmail.com"}, interactive=True)
# → abre browser con consentimiento visible, state+PKCE, callback local,
#   tokens cifrados FUERA de OKF, auth_mode == "oauth".
# Este ejemplo es especificación aspiracional; afirmar que funciona hoy es un error.
```

## Do / Don't

**Do**

- Resolver credenciales **solo** por referencia `env://NOMBRE` y materializarlas en el momento de uso, nunca antes.
- Retornar un dict público idempotente y persistible en `account_store`.
- Fallar con errores tipados y `code` estable (`unsupported_provider`, `missing_credential_ref`, `missing_email`, `not_interactive`, `connection_failed`).
- Documentar OAuth como futuro y condicionar todo lo OAuth a los requisitos 1–7 de `## Interface`.
- Requerir consentimiento visible del usuario para cualquier flujo de autorización futura.

**Don't**

- No pedir, imprimir, loguear ni persistir contraseñas en claro — ni siquiera en modo `interactive`.
- No almacenar refresh tokens (ni tokens) dentro de OKF o del dict de cuenta pública.
- No implementar OAuth headless/silencioso ni sin `state`/PKCE cuando llegue el momento.
- No inventar compatibilidad con proveedores distintos de Gmail/Outlook.
- No mutar `account_hint` ni retornar secretos "por conveniencia".
- No afirmar en docs ni logs que OAuth existe hoy.

## Tests

Propuestas (sin implementar aquí; ningún test existente debe modificarse para este contrato):

1. **Sin secretos**: llamar con `credential_ref` válida y afirmar que el resultado no contiene ninguna clave con valor materializado de entorno (`password`, `token`, `refresh_token`) y que sí contiene la referencia `env://...` intacta.
2. **Compatibilidad `account_store`**: el dict retornado pasa la validación/esquema de `account_store` tal cual (round-trip save/load sin campos secretos).
3. **`account_hint` inmutable**: el dict de entrada es idéntico antes y después de la llamada.
4. **`interactive=False`**: sin credencial disponible → `ProviderConnectionError` con `code == "missing_credential_ref"`; sin `email` → `code == "missing_email"`; nunca bloquea esperando entrada.
5. **Proveedor soportado**: `"gmail"` y `"outlook"` aceptados; cualquier otro → `code == "unsupported_provider"`.
6. **Sin credencial en el entorno**: si `env://NOMBRE` no existe en el entorno → `code == "connection_failed"` o error equivalente, y el mensaje **no** contiene el nombre resuelto ni valor alguno.
7. **Invariantes de log**: capturar stdout/stderr durante conexiones exitosas y fallidas y afirmar que nunca aparece una contraseña ni un token.
8. **(Futuro, se añaden cuando exista OAuth)**: `state` presente y único, PKCE S256, callback solo en loopback, tokens cifrados y fuera de OKF, revocación borra almacén local, scopes = mínimos declarados.

## Constraints

- **Alcance de este contrato**: solo documentación de interfaz, estado real y diseño futuro. **No implementa OAuth, ni callback local, ni almacenamiento cifrado de tokens, ni modifica código, tests ni la CLI.**
- La CLI actual debe seguir resolviendo credenciales por `env://NOMBRE`; cualquier cambio de ese comportamiento sale de este contrato.
- El resultado debe seguir siendo una cuenta pública sin secretos y persistible en `account_store`.
- Gmail/Outlook vía IMAP/SMTP es la única capacidad real; `auth_mode` es `"env-credential"` hasta que OAuth esté implementado y probado.
- **PARAR y reportar si**: alguien pide implementar OAuth/PKCE/callback como parte de este contrato; si hay que pedir, imprimir o persistir una contraseña en claro; si hay que almacenar tokens dentro de OKF; si el resultado de `connect_provider` tendría que incluir secretos; o si el entorno no permite mantener `account_hint` inmutable y el dict retornado libre de secretos — en cualquiera de esos casos, PARAR y reportar al usuario antes de continuar.