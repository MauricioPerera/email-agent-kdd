---
task: sync-cursor
intent: gestionar el cursor de sincronizacion IMAP por cuenta en root/.email-agent/cursors.json de forma atomica
target: ../../../../src/email/cursor_store.py
signature: "def load_sync_cursor(root: str, account_id: str) -> int"
language: python
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 80
  params_max: 3
deps_allowed: [os, pathlib, json, re]
forbids: [eval, exec, subprocess, network_access, socket, pickle]
tests_frozen: true
tests: tests/frozen_sync_cursor.py
test_command: "python -m pytest tests/frozen_sync_cursor.py -q"
stop_rule: "PARAR y reportar si algún invariant resulta insatisfacible dentro del presupuesto, si el store ya mantiene cursores en otra ubicación/formato (no root/.email-agent/cursors.json), o si el esquema corrupto no puede distinguirse de un archivo válido sin romper el contrato."
---

## Intent

Par de funciones que gestionan el cursor de sincronización IMAP de cada cuenta:

- `load_sync_cursor(root: str, account_id: str) -> int` devuelve el último `uid` procesado de
  `account_id` leído de `root/.email-agent/cursors.json`; `0` si el archivo no existe o la cuenta
  no tiene entrada.
- `save_sync_cursor(root: str, account_id: str, uid: int) -> str` reemplaza (o crea) la entrada de
  `account_id` con `uid`, preservando las demás cuentas, y escribe el JSON completo de forma
  atómica y determinista. Devuelve la ruta del fichero escrito.

Este módulo NO toca IMAP, no decide qué mensajes procesar (eso vive en `fetch-imap-messages` con su
`since_uid`) y no conoce cuentas ni credenciales: solo persiste el número.

## Interface

`def load_sync_cursor(root: str, account_id: str) -> int`

- `root`: raíz explícita del proyecto (str no vacío). El fichero vive SIEMPRE en
  `root/.email-agent/cursors.json`. Sin raíz implícita, ni cwd, ni `~`, ni variables de entorno.
- `account_id`: str no vacío que debe matchear por completo `^[A-Za-z0-9_.-]{1,64}$` y, además, no
  ser exactamente `.` ni `..` (se rechazan explícitamente aunque el patrón los acepte) ni contener
  separadores de ruta (`/`, `\`).
- Devuelve: `int` — el uid persistido, o `0` si el archivo no existe (incluye `root` aún no creado)
  o la cuenta no tiene entrada dentro de un archivo válido.
- Lanza: `ValueError` por argumentos inválidos (validado ANTES de tocar disco); `RuntimeError` si el
  archivo existe pero su JSON no parsea o su esquema no es exactamente el pactado.

`def save_sync_cursor(root: str, account_id: str, uid: int) -> str`

- `uid`: `int` NO `bool` (`True`/`False` se rechazan) y `>= 0`; `0` es válido (reinicia el cursor).
- Devuelve: `str` — la ruta del fichero escrito, exactamente `str(Path(root) / ".email-agent" / "cursors.json")`.
- Lanza: `ValueError` por argumentos inválidos (validado ANTES de tocar disco); `RuntimeError` si el
  archivo previo existe y está corrupto (JSON o esquema): NUNCA se sobreescribe en silencio un
  estado ilegible; `OSError` propagada si el sistema de archivos falla.

Esquema exacto del fichero (única forma válida):

```json
{"cursors": {"<account_id>": <uid>}}
```

Serialización canónica (determinista, byte a byte para el mismo estado):

```python
json.dumps({"cursors": cursors}, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
```

codificado en UTF-8 **SIN salto de línea final**: el fichero termina exactamente en el último byte
del JSON (nada de `\n` final). No se escriben marcas de tiempo, versiones, metadatos ni claves
adicionales.

## Invariants

- **Ubicación fija**: el estado vive exactamente en `<root>/.email-agent/cursors.json`; nunca en otra
  ruta ni con subdirectorios derivados de la cuenta. `save` crea `.email-agent/` (y `root`, con
  `os.makedirs(..., exist_ok=True)`) si falta; `load` no crea nada.
- **Esquema exacto**: un archivo válido es un dict con la única clave `cursors`, cuyo valor es un
  dict `account_id -> uid`. Cualquier otra forma — clave raíz distinta o adicional, `cursors` ausente
  o no dict, valor que no sea `int` no `bool` `>= 0` (también en cuentas ajenas a la consultada),
  clave que no matchee el patrón de `account_id` o sea exactamente `.`/`..` — es esquema corrupto →
  `RuntimeError`. Un uid negativo o booleano dentro del archivo es corrupción, no dato.
- **Ausencia = 0**: archivo inexistente o cuenta sin entrada dentro de un archivo válido devuelven
  `0`. La ausencia NUNCA es error ni dispara creación de ficheros.
- **Reemplazo quirúrgico**: `save` solo cambia la entrada de `account_id`; las demás cuentas y sus
  uids quedan byte a byte intactos en el resultado. Guardar el mismo `(account_id, uid)` de nuevo
  produce un archivo idéntico (idempotencia).
- **Validación antes de disco**: todas las validaciones de argumentos (`root`/`account_id` no vacíos,
  patrón de `account_id`, tipo y rango de `uid`) ocurren ANTES de leer o escribir nada; una llamada
  inválida no crea directorios ni ficheros ni toca el estado existente.
- **Escritura atómica**: `save` escribe a un fichero temporal en el MISMO directorio y remata con
  `os.replace`; nunca queda un `cursors.json` a medio escribir ni escrituras parciales tras fallo
  (el estado previo se conserva si la escritura falla).
- **Determinismo**: misma secuencia de `save` → mismos bytes siempre. Sin fechas, sin aleatoriedad
  en el contenido, sin dependencia del orden de inserción (`sort_keys`), sin estado global.
- **Sin secretos ni red**: el fichero solo contiene ids de cuenta y uids; nada de contraseñas,
  tokens, hosts ni contenido de mensajes. Sin red, sin subprocess, sin eval/exec.
- **Pureza**: `load` no muta nada en disco; `save` solo toca `cursors.json` y su fichero temporal
  (limpiando el temporal si la escritura falla).

## Examples

- `load_sync_cursor("/proy", "gmail-1")` con `/proy/.email-agent/cursors.json` inexistente → `0`.
- `save_sync_cursor("/proy", "gmail-1", 42)` crea `/proy/.email-agent/cursors.json` con contenido
  `{"cursors":{"gmail-1":42}}` y devuelve `/proy/.email-agent/cursors.json`; después
  `load_sync_cursor("/proy", "gmail-1")` → `42`.
- `save_sync_cursor("/proy", "b", 7)` tras guardar `a=1`: el archivo queda `{"cursors":{"a":1,"b":7}}`
  (claves ordenadas por `sort_keys`); `load_sync_cursor("/proy", "a")` sigue → `1`.
- `save_sync_cursor("/proy", "a", 3)` de nuevo: `a` pasa a `3`, `b` queda `7` intacto.
- Re-guardar `("a", 3)` otra vez: bytes del fichero idénticos (idempotencia).
- `save_sync_cursor("/proy", "a", 0)` es válido: reinicia el cursor de `a` a `0`.
- `load_sync_cursor("/proy", "c")` con `a=1, b=7` en el fichero → `0` (cuenta ausente, no error).
- `save_sync_cursor("", "a", 1)`, `save_sync_cursor("/proy", "", 1)`,
  `save_sync_cursor("/proy", "../x", 1)`, `save_sync_cursor("/proy", ".", 1)`,
  `save_sync_cursor("/proy", "..", 1)`, `save_sync_cursor("/proy", "a b", 1)`,
  `save_sync_cursor("/proy", "a" * 65, 1)` → `ValueError`, sin crear nada en disco. (`.` y `..`
  matchean el patrón pero se rechazan explícitamente.)
- `save_sync_cursor("/proy", "a", True)` → `ValueError` (bool NO es uid); igual con `-1`, `"5"`,
  `5.0` y `None`.
- `load_sync_cursor("", "a")` y `load_sync_cursor("/proy", "")` → `ValueError` antes de disco.
- Fichero con `{no-json`, con `{"cursor":{"a":1}}` (clave raíz equivocada), con `{"cursors":[]}` o con
  `{"cursors":{"a":true}}` → `load_sync_cursor` y `save_sync_cursor` → `RuntimeError`; el archivo
  corrupto NO se sobreescribe ni se borra.

## Do / Don't

**Do**
- Validar `root` (no vacío), `account_id` (no vacío + `re.fullmatch(r"[A-Za-z0-9_.-]{1,64}")` +
  rechazo explícito de `.` y `..`) y `uid` (`int`, no `bool`, `>= 0`) al principio de cada función,
  antes de cualquier acceso a disco.
- Usar `pathlib` para construir la ruta y `os.makedirs(..., exist_ok=True)` para crear
  `.email-agent/` solo en `save`.
- Leer el estado previo en `save`, verificar el esquema con la misma regla de `load`, reemplazar solo
  la cuenta y serializar con `json.dumps(..., sort_keys=True, ensure_ascii=True, separators=(",", ":"))`.
- Escribir atómicamente: fichero temporal en el mismo directorio + `os.replace`, limpiando el
  temporal si algo falla.
- Convertir `json.JSONDecodeError` en `RuntimeError` con un mensaje claro, y validar el esquema
  completo del dict `cursors` (todas las cuentas, no solo la consultada).

**Don't**
- No abras conexiones IMAP/SMTP, no hagas red, no uses subprocess/eval/exec ni importes el módulo de
  fetch: este módulo es persistencia pura del número.
- No escribas secretos, credenciales, hosts, fechas, timestamps ni claves extra en `cursors.json`.
- No devuelvas `0` ante un archivo corrupto: corrupción es `RuntimeError`, solo la ausencia es `0`.
- No sobreescribas un `cursors.json` corrupto en `save` ni lo borres; PARAR con `RuntimeError`.
- No aceptes `root`/`account_id` vacíos, `account_id` con separadores de ruta (`/`, `\`) o exactamente
  `.`/`..`, más de 64 chars, ni `uid` booleano/negativo/float/str: `ValueError` antes de disco.
- No uses escritura directa (`open(path, "w")` sobre el destino final): siempre temporal + replace.

## Tests

Property-tests congelados (oráculo independiente, sin importar nada del target):

```python
# tests/frozen_sync_cursor.py
import json
import os
import pytest

from src.email.cursor_store import load_sync_cursor, save_sync_cursor


def _path(root):
    return root / ".email-agent" / "cursors.json"


def test_ausencia_devuelve_cero(tmp_root):
    assert load_sync_cursor(str(tmp_root), "gmail-1") == 0


def test_save_estructura_ubicacion_y_carga(tmp_root):
    ruta = save_sync_cursor(str(tmp_root), "gmail-1", 42)
    assert ruta == str(_path(tmp_root))
    assert load_sync_cursor(str(tmp_root), "gmail-1") == 42
    data = json.loads(_path(tmp_root).read_text(encoding="utf-8"))
    assert data == {"cursors": {"gmail-1": 42}}


def test_reemplazo_quirurgico_y_orden(tmp_root):
    save_sync_cursor(str(tmp_root), "b", 7)
    save_sync_cursor(str(tmp_root), "a", 1)
    save_sync_cursor(str(tmp_root), "a", 3)
    raw = _path(tmp_root).read_text(encoding="utf-8")
    assert json.loads(raw) == {"cursors": {"a": 3, "b": 7}}
    assert raw.index('"a"') < raw.index('"b"')  # sort_keys


def test_cuenta_ausente_devuelve_cero(tmp_root):
    save_sync_cursor(str(tmp_root), "a", 1)
    assert load_sync_cursor(str(tmp_root), "c") == 0


def test_idempotencia_bytes(tmp_root):
    save_sync_cursor(str(tmp_root), "a", 1)
    primero = _path(tmp_root).read_bytes()
    save_sync_cursor(str(tmp_root), "a", 1)
    assert _path(tmp_root).read_bytes() == primero


def test_validacion_antes_de_disco(tmp_root):
    with pytest.raises(ValueError): load_sync_cursor("", "a")
    with pytest.raises(ValueError): load_sync_cursor(str(tmp_root), "")
    with pytest.raises(ValueError): load_sync_cursor(str(tmp_root), "../x")
    with pytest.raises(ValueError): load_sync_cursor(str(tmp_root), "a" * 65)
    with pytest.raises(ValueError): save_sync_cursor("", "a", 1)
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "", 1)
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "a b", 1)
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "a", True)
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "a", -1)
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "a", "5")
    with pytest.raises(ValueError): save_sync_cursor(str(tmp_root), "a", 5.0)
    assert not _path(tmp_root).exists()


def test_runtimeerror_json_o_esquema_corrupto(tmp_root):
    _path(tmp_root).parent.mkdir(parents=True, exist_ok=True)
    for corrupto in (
        "{no-json",
        json.dumps({"cursor": {"a": 1}}),
        json.dumps({"cursors": []}),
        json.dumps({"cursors": {"a": True}}),
        json.dumps({"cursors": {"a": -1}}),
        json.dumps({"cursors": {"a": 1, "b": "2"}}),
    ):
        _path(tmp_root).write_text(corrupto, encoding="utf-8")
        with pytest.raises(RuntimeError):
            load_sync_cursor(str(tmp_root), "a")
        with pytest.raises(RuntimeError):
            save_sync_cursor(str(tmp_root), "a", 2)
        assert _path(tmp_root).read_text(encoding="utf-8") == corrupto  # intacto


def test_escritura_atomica_sin_parciales(tmp_root, monkeypatch):
    save_sync_cursor(str(tmp_root), "a", 1)
    antes = _path(tmp_root).read_bytes()

    def boom(src, dst):
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        save_sync_cursor(str(tmp_root), "a", 5)
    assert _path(tmp_root).read_bytes() == antes
    assert not list(_path(tmp_root).parent.glob("*.tmp"))
```

## Constraints

- Presupuestos: ciclomática ≤ 12, anidamiento ≤ 3, líneas ≤ 80, parámetros ≤ 3 por función.
- Solo dependencias de `deps_allowed` (`os`, `pathlib`, `json`, `re`); cero terceros
  (anti-slopsquatting).
- Prohibido: `eval`, `exec`, `subprocess`, red, `socket`, `pickle`, credenciales/secretos, fechas o
  marcas de tiempo en el fichero.
- Rendimiento: O(n) sobre el número de cuentas del fichero; sin estado global ni locks. La escritura
  atómica es la única garantía de concurrencia (un solo escritor por fichero).
- Límites del MVP: sin historial de cursores (solo último uid por cuenta), sin borrado de cuentas
  (no hay API de delete), sin migración de formatos previos y sin bloqueo entre procesos.
- PARAR y reportar si cualquier condición de la sección final se cumple; en ese caso no se
  implementa nada y se devuelve el contrato con el motivo.

## PARAR y reportar si

- El proyecto ya persiste cursores en otra ubicación o formato (p. ej. dentro de la cuenta en
  `root/.email-agent/accounts.json`) → PARAR y reportar antes de crear un segundo origen de verdad.
- `save_sync_cursor` no puede preservar las cuentas ajenas dentro del presupuesto (p. ej. el esquema
  real del fichero difiere del pactado) → PARAR y reportar el esquema real.
- La distinción entre "archivo ausente" y "archivo corrupto" no es posible con la API disponible
  (`Path.exists` + `json.loads`) → PARAR y reportar en lugar de tragarse la corrupción como `0`.
- La escritura atómica temporal + `os.replace` no es viable en el filesystem destino → PARAR y
  reportar, no caer a escritura directa en silencio.
- Alguna regla de Invariants resulta insatisfacible en código (ciclomática/anidamiento/líneas por
  encima del presupuesto) → PARAR y pedir excepción, no improvisar.