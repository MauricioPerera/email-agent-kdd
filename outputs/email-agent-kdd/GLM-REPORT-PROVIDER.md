# GLM-REPORT-PROVIDER

## Resumen

Frontera de proveedor definida como interfaz minima y estructural: `EmailProvider(Protocol)` (solo stdlib `typing`, decorado `@runtime_checkable`) con exactamente dos metodos publicos: `list_messages(account: dict, query: str = "") -> list[dict]` y `send_message(account: dict, message: dict) -> dict`. Cero implementacion de red: cuerpos solo docstring + `...`. Los dicts (`account`, `message`, recibo) quedan documentados como serializables a JSON; `send_message` recibe una orden YA confirmada (`message["confirmed"] is True`) y la interfaz no ofrece ningun camino para saltarse la confirmacion (los adaptadores deben rechazar orden sin confirmar con `ValueError`). `credential_ref` sigue opaco. No se tomó ninguna decision de proveedor concreto (SMTP/IMAP/OAuth quedan fuera de la frontera), por lo que no fue necesario detenerse.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/email-provider.md` (nuevo)
- `outputs/email-agent-kdd/tests/frozen_email_provider.py` (nuevo)
- `src/email/provider.py` (nuevo)
- `outputs/email-agent-kdd/GLM-REPORT-PROVIDER.md` (nuevo)

## Verificación

- Suite congelada completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **62 passed** (8 del nuevo contrato + 54 previos, sin regresiones).
- El oráculo NO importa el target ni `src.email`: congela el contrato (frontmatter con budgets/deps/forbids, 7 secciones, `PARAR y reportar si`, bloques frozen) y congela la interfaz parseando `src/email/provider.py` por AST sin importarlo ni ejecutarlo: clase unica `EmailProvider` heredando solo `Protocol` con `@runtime_checkable`, imports exclusivos de `typing`, firmas exactas (parametros y defaults) de ambos metodos, cuerpos sin implementacion (solo docstring/`...`), y ausencia de `smtplib`, `socket`, `urllib`, `requests`, `imaplib`, `poplib`, `subprocess`, `eval`, `exec`, `open`, `print`, `connect`, `login`, `send`.
- Verificaciones de semantica en el oráculo: dicts frozen serializables a JSON con `json.dumps`, orden frozen con `confirmed: true`, `account` con exactamente las 5 claves del registro de `create_email_account` y `status: "disconnected"`, reglas de orden confirmada/recibo/don't de enviar sin confirmacion/rechazo con `ValueError`, opacidad de `credential_ref`, pureza (sin disco, sin mutar entrada) y `query` con default vacio documentado.
- Presupuesto del target: 31 lineas (<= 80), ciclomatica 1, anidamiento 0, max 3 parametros por metodo (<= 5).

## Estado

LISTO — 4 entregables creados, suite congelada 62/62 en verde, sin dependencias externas ni red, sin archivos existentes modificados.