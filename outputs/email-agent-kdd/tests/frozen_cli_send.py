# frozen_cli_send.py — Oracle independiente para el contrato cli-send.
# NO importa src.email. NO abre red. Sin dependencias fuera de pytest + stdlib.
#
# Capa 1 (estructural, siempre corre): parsea el contrato
#   knowledge/contracts/cli-send.md y congela sus declaraciones
#   (frontmatter target/firma, 7 secciones, frase PARAR y reportar si,
#   comandos, códigos 0/1/2, confirmación exacta, sin adjuntos,
#   secretos fuera de salida, sync/search/account intactos).
# Capa 2 (comportamiento): solo se ejecuta si src/email/cli.py existe Y su
#   texto declara las ramas draft/send; de lo contrario pytest.skip.

import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent                    # outputs/email-agent-kdd
CONTRACT_PATH = PKG_DIR / "knowledge" / "contracts" / "cli-send.md"
REPO_ROOT = TESTS_DIR.parents[2]              # 2026-09-10/l
CLI_PATH = REPO_ROOT / "src" / "email" / "cli.py"

# ---- Constantes congeladas (fuente de verdad: cli-send.md) -----------------

CONTRACT_SECTIONS = [
    "## Intent",
    "## Interface",
    "## Invariants",
    "## Examples",
    "## Do / Don't",
    "## Tests",
    "## Constraints",
]

STOP_PHRASE = "PARAR y reportar si"

TARGET_SUFFIX = "src/email/cli.py"
SIGNATURE = "def cli_main(argv: list) -> int"

DRAFT_ARGV = ["draft", "ROOT", "ACCOUNT_ID", "TO", "SUBJECT", "BODY"]
SHOW_DRAFT_ARGV = ["draft", "show", "ROOT", "DRAFT_ID"]
SEND_ARGV = ["send", "ROOT", "ACCOUNT_ID", "DRAFT_ID", "CONFIRMAR_ENVIO"]

CONFIRM_PHRASE = "CONFIRMAR ENVIO"          # exacta: mayúsculas + acento
CONFIRM_REJECTS = [
    "confirmar envio",    # minúsculas
    "CONFIRMAR ENVIOS",   # desliz
    "CONFIRMAR  ENVIO",   # doble espacio
    "CONFIRMARENVIOS",    # sin espacio
    "CONFIRMAR ENVÍO",    # acento añadido
    "",                   # vacío
    "yes",
    "y",
]

EXIT_OK = 0
EXIT_OP_ERROR = 1        # draft inexistente, confirmación incorrecta, fallo envío
EXIT_USAGE = 2           # argv vacío, subcomando desconocido, aridad equivocada

USAGE_BAD_CASES = [
    [],
    ["bogus"],
    ["draft"],
    ["draft", "ROOT", "ACC"],
    ["send"],
    ["send", "ROOT", "ACC"],
]

# Adjuntos: fuera del MVP. La CLI no los acepta ni los silenciona -> código 2.
ATTACHMENT_HINT_TOKENS = ["--attach", "attachment", "adjunto", "adjuntos"]

# Contactos salientes post-envío: delegación en orden y UNA llamada al store.
EXTRACT_DELEGATION = "`extract_outgoing_contacts(confirmed)`"
STORE_DELEGATION = "`store_email_contacts(root, contacts)`"
STORE_ONCE_PHRASE = "una sola vez"
EMPTY_LIST_PHRASE = "lista vacía"
NO_AUTO_RETRY_PHRASE = "no debe reintentar automáticamente"
SMTP_MAY_HAVE_SENT_PHRASE = "ya pudo haber enviado"
SENT_JSON_KEYS = {"id", "status"}

COMPAT_MODULES = {
    "sync": ["sync_mail"],
    "search": ["search_messages"],
    "account": ["load_account"],
}

SECRETS_FORBIDDEN_SUBSTRINGS = ["password", "passwd", "secret", "token"]

# ---- Carga del contrato -----------------------------------------------------


def _contract_text() -> str:
    if not CONTRACT_PATH.is_file():
        pytest.fail(f"contrato ausente: {CONTRACT_PATH}")
    return CONTRACT_PATH.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    assert m is not None, "el contrato no tiene frontmatter YAML delimitado por ---"
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-", "\t")):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm


# ---- Capa 1: estructura del contrato ---------------------------------------


def test_contrato_existe_y_no_vacio():
    text = _contract_text()
    assert len(text.strip()) > 200


def test_frontmatter_target_y_firma():
    fm = _frontmatter(_contract_text())
    assert fm.get("task") == "cli-send"
    target = fm.get("target", "").replace("\\", "/")
    assert target.endswith(TARGET_SUFFIX), f"target incorrecto: {target!r}"
    assert fm.get("signature") == SIGNATURE


def test_las_siete_secciones_estan_en_orden():
    text = _contract_text()
    pos = -1
    for section in CONTRACT_SECTIONS:
        cur = text.find(section)
        assert cur != -1, f"falta la seccion {section!r}"
        assert cur > pos, f"seccion fuera de orden: {section!r}"
        pos = cur


def test_frase_parar_y_reportar_si():
    text = _contract_text()
    assert STOP_PHRASE in text, (
        "el contrato no contiene la frase de parada "
        f"{STOP_PHRASE!r} (regla de conflicto firma/dependencia/entorno)"
    )


def test_comandos_draft_y_send_congelados():
    text = _contract_text()
    assert "`draft ROOT ACCOUNT_ID TO SUBJECT BODY`" in text
    assert "`send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR_ENVIO`" in text
    assert DRAFT_ARGV[0] == "draft" and len(DRAFT_ARGV) == 6
    assert SEND_ARGV[0] == "send" and len(SEND_ARGV) == 5


def test_codigos_de_salida_0_1_2_congelados():
    text = _contract_text()
    assert "| `0` |" in text and "| `1` |" in text and "| `2` |" in text
    assert (EXIT_OK, EXIT_OP_ERROR, EXIT_USAGE) == (0, 1, 2)


def test_confirmacion_exacta_sin_normalizacion():
    text = _contract_text()
    assert f"`{CONFIRM_PHRASE}`" in text or CONFIRM_PHRASE in text
    assert "No normalizar la frase de confirmación" in text
    assert ".lower()" in text and ".strip()" in text  # prohibidos explícitamente
    for bad in CONFIRM_REJECTS:
        assert bad != CONFIRM_PHRASE


def test_adjuntos_fuera_del_mvp():
    text = _contract_text()
    assert "Adjuntos rechazados" in text
    assert "Sin adjuntos en el MVP" in text
    # Nombrar "adjunto" al DOCUMENTAR que quedan fuera esta bien; lo que no
    # puede haber es flags o sintaxis de adjuntos definidas en el contrato.
    assert re.search(r"--attach\w*", text, flags=re.IGNORECASE) is None
    assert re.search(r"--adjuntos?", text, flags=re.IGNORECASE) is None
    assert re.search(r"\battachments?\s*=", text, flags=re.IGNORECASE) is None


def test_secretos_ausentes_de_la_salida():
    text = _contract_text()
    assert "Secretos fuera de salida" in text
    assert "Sin persistencia de credenciales" in text
    assert "credencial SOLO en memoria" in text


def test_compatibilidad_sync_search_account():
    text = _contract_text()
    assert "`sync`, `search` y `account`" in text or "sync`/`search`/`account`" in text
    for mod_name, fns in COMPAT_MODULES.items():
        assert mod_name in text
        for fn in fns:
            assert fn in text, f"el contrato no congela {mod_name}.{fn}"


# ---- Capa 1 (añadido): contactos salientes post-envío ----------------------


def test_contrato_congela_delegacion_post_envio():
    text = _contract_text()
    assert EXTRACT_DELEGATION in text, (
        "el contrato no congela la delegacion en extract_outgoing_contacts(confirmed)"
    )
    assert STORE_DELEGATION in text, (
        "el contrato no congela la delegacion en store_email_contacts(root, contacts)"
    )
    assert STORE_ONCE_PHRASE in text.lower(), (
        "el contrato no exige UNA sola llamada al store"
    )


def test_contrato_define_lista_vacia_y_fallo_del_store():
    text = _contract_text()
    assert EMPTY_LIST_PHRASE in text, "el contrato no define el caso de lista vacia"
    assert NO_AUTO_RETRY_PHRASE in text.lower(), (
        "el contrato no documenta la prohibicion de reintentar automaticamente"
    )
    assert SMTP_MAY_HAVE_SENT_PHRASE in text, (
        "el contrato no documenta que el SMTP ya pudo haber enviado"
    )
    assert "sin traceback" in text.lower()
    assert "código `1`" in text or "codigo `1`" in text or "| `1` |" in text


# ---- Capa 2: comportamiento (skip mientras no existan las ramas) ------------


def _cli_has_draft_send_branches() -> bool:
    """Detección por TEXTO (sin importar src.email) de las ramas draft/send."""
    if not CLI_PATH.is_file():
        return False
    text = CLI_PATH.read_text(encoding="utf-8")
    return ('"draft"' in text or "'draft'" in text) and (
        '"send"' in text or "'send'" in text
    )


def _load_cli():
    """Importa src.email.cli SOLO si existen las ramas draft/send. Si no, None."""
    if not _cli_has_draft_send_branches():
        return None
    sys.path.insert(0, str(PKG_DIR / "src"))
    try:
        spec = importlib.util.spec_from_file_location(
            "frozen_oracle_email_cli", CLI_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod if hasattr(mod, "cli_main") else None
    except Exception:
        return None


def _skip_if_no_branches():
    if not _cli_has_draft_send_branches():
        pytest.skip(
            "src/email/cli.py no existe todavia o no declara las ramas draft/send; "
            "test de comportamiento diferido"
        )


@pytest.fixture
def cli():
    mod = _load_cli()
    if mod is None:
        pytest.skip(
            "src/email/cli.py no existe todavia o no declara las ramas draft/send; "
            "test de comportamiento diferido"
        )
    return mod


@pytest.fixture
def tmp_root(tmp_path):
    return tmp_path


def test_draft_devuelve_0_y_persiste_un_json(cli, tmp_root, capsys):
    rc = cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    assert rc == EXIT_OK
    drafts = list((tmp_root / "drafts").glob("*.json"))
    assert len(drafts) == 1
    contenido = drafts[0].read_text(encoding="utf-8")
    relectura = json.loads(contenido)
    capsys.readouterr()  # descarta la salida de la 1a invocacion
    # idempotente: re-escribir el mismo id produce el mismo byte-stream
    rc2 = cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    assert rc2 == EXIT_OK
    assert contenido == drafts[0].read_text(encoding="utf-8")
    out = capsys.readouterr().out.strip()  # solo la 2a invocacion
    lineas = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lineas) == 1
    emitted = json.loads(lineas[0])
    assert emitted["id"] == relectura.get("id", emitted["id"])
    assert Path(emitted["path"]).is_file()
    low = json.dumps(relectura).lower()
    for bad in SECRETS_FORBIDDEN_SUBSTRINGS:
        assert bad not in low


def test_draft_show_muestra_previsualizacion_sin_mutar(cli, tmp_root, capsys):
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_path = next((tmp_root / "drafts").glob("*.json"))
    draft_id = draft_path.stem
    original = draft_path.read_bytes()
    capsys.readouterr()

    rc = cli.cli_main(["draft", "show", str(tmp_root), draft_id])

    assert rc == EXIT_OK
    assert json.loads(capsys.readouterr().out) == json.loads(original)
    assert draft_path.read_bytes() == original


def test_draft_show_rechaza_id_invalido_y_no_sale_de_drafts(cli, tmp_root, capsys):
    rc = cli.cli_main(["draft", "show", str(tmp_root), "../secreto"])
    assert rc == EXIT_OP_ERROR
    assert "traceback" not in capsys.readouterr().err.lower()
    assert not (tmp_root.parent / "secreto.json").exists()


def test_draft_show_inexistente_devuelve_1(cli, tmp_root, capsys):
    rc = cli.cli_main(["draft", "show", str(tmp_root), "0" * 64])
    assert rc == EXIT_OP_ERROR
    assert "traceback" not in capsys.readouterr().err.lower()


def test_draft_show_no_expone_campos_extra_del_archivo(cli, tmp_root, capsys):
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_path = next((tmp_root / "drafts").glob("*.json"))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["credential_ref"] = "env://NO-DEBE-SALIR"
    draft["internal_note"] = "dato interno"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    capsys.readouterr()

    assert cli.cli_main(["draft", "show", str(tmp_root), draft_path.stem]) == EXIT_OK
    preview = json.loads(capsys.readouterr().out)
    assert "credential_ref" not in preview
    assert "internal_note" not in preview
    assert preview["subject"] == "Hola"


def _stub_backend(monkeypatch, cli):
    """Aisla la rama send de red y store real: cuenta fixa, credencial
    marcador y SMTP stub. NO cambia el comportamiento del cli (solo sus
    dependencias inyectadas por import)."""
    cuenta = {
        "account_id": "acc-1",
        "provider": "gmail",
        "email": "me@example.com",
        "credential_ref": "env://TEST",
    }
    monkeypatch.setattr(cli, "load_email_accounts", lambda root: [dict(cuenta)])
    monkeypatch.setattr(
        cli, "resolve_credential", lambda ref: "MARCADOR-ORACLE-NO-SECRETO"
    )
    monkeypatch.setattr(
        cli, "send_smtp_message", lambda account, config, mensaje: None
    )


def test_send_rechaza_confirmacion_inexacta_sin_tocar_red(cli, tmp_root):
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    for frase in CONFIRM_REJECTS:
        rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, frase])
        assert rc == EXIT_OP_ERROR, f"frase {frase!r} debe ser rechazada con 1"


def test_send_confirmado_devuelve_0_con_json(cli, tmp_root, capsys, monkeypatch):
    _stub_backend(monkeypatch, cli)
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    capsys.readouterr()  # descarta la salida del draft: solo evalua el send
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    assert rc == EXIT_OK
    lineas = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lineas) == 1
    assert json.loads(lineas[0])["id"] == draft_id


def test_send_draft_inexistente_devuelve_1(cli, tmp_root, capsys):
    rc = cli.cli_main(
        ["send", str(tmp_root), "acc-1", "no-existe", CONFIRM_PHRASE]
    )
    assert rc == EXIT_OP_ERROR
    err = capsys.readouterr().err.lower()
    assert "traceback" not in err


def test_uso_incorrecto_devuelve_2(cli, tmp_root):
    for argv in USAGE_BAD_CASES:
        assert cli.cli_main(argv) == EXIT_USAGE, f"argv {argv!r} debe dar 2"


def test_adjuntos_rechazados_con_2(cli, tmp_root):
    for tok in ATTACHMENT_HINT_TOKENS:
        assert cli.cli_main([tok, "ROOT"]) == EXIT_USAGE, f"{tok!r} debe dar 2"


def test_secretos_nunca_en_salida(cli, tmp_root, capsys, monkeypatch):
    _stub_backend(monkeypatch, cli)  # sin red; la rama send corre real
    secreto = "S3CR3T0-CLAVE"
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()
    assert secreto not in capturado.out
    assert secreto not in capturado.err
    for f in (tmp_root / "drafts").glob("*.json"):
        assert secreto not in f.read_text(encoding="utf-8")
    assert rc in (EXIT_OK, EXIT_OP_ERROR)


def test_sync_search_account_intactos():
    _skip_if_no_branches()
    sys.path.insert(0, str(PKG_DIR / "src"))
    for mod_name, fns in COMPAT_MODULES.items():
        path = PKG_DIR / "src" / "email" / f"{mod_name}.py"
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nombres = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for fn in fns:
            assert fn in nombres, f"{mod_name}.{fn} desaparecio (contrato la congela)"


def test_send_draft_con_adjuntos_devuelve_2_sin_backend_ni_secretos(
    cli, tmp_root, capsys, monkeypatch
):
    """Un draft pending con la clave attachments (fuera del MVP) es rechazado
    con codigo 2 ANTES de tocar el backend: sin resolucion de credencial, sin
    SMTP y sin secretos en la salida."""
    marcador_secret = "MARCADOR-SECRETO-ORACLE"
    llamadas = {"load": [], "resolve": [], "smtp": []}
    cuenta = {
        "account_id": "acc-1",
        "provider": "gmail",
        "email": "me@example.com",
        "credential_ref": "env://TEST",
        "smtp_host": "smtp.gmail.com",
    }
    monkeypatch.setattr(
        cli, "load_email_accounts", lambda root: llamadas["load"].append(root) or [cuenta]
    )
    monkeypatch.setattr(
        cli,
        "resolve_credential",
        lambda ref: llamadas["resolve"].append(ref) or marcador_secret,
    )
    monkeypatch.setattr(
        cli,
        "send_smtp_message",
        lambda account, config, mensaje: llamadas["smtp"].append((account, config)),
    )

    # Draft pending con attachments, mismo id determinista que congela el
    # contrato (sha256 de account_id|to|subject|body) pero escrito a mano:
    # el oráculo no importa src.email.
    to_norm = ["a@b.c"]
    payload = "acc-1|" + ",".join(to_norm) + "|Hola|Cuerpo"
    draft_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    draft = {
        "id": draft_id,
        "account_id": "acc-1",
        "to": to_norm,
        "subject": "Hola",
        "body": "Cuerpo",
        "status": "pending",
        "attachments": ["factura.pdf"],
    }
    drafts_dir = tmp_root / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    (drafts_dir / (draft_id + ".json")).write_text(
        json.dumps(draft, sort_keys=True), encoding="utf-8"
    )

    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])

    assert rc == EXIT_USAGE, "adjuntos fuera del MVP -> codigo 2"
    assert llamadas["resolve"] == [], "no se debe resolver ninguna credencial"
    assert llamadas["smtp"] == [], "no se debe llamar a SMTP"
    capturado = capsys.readouterr()
    for secreto in [marcador_secret] + SECRETS_FORBIDDEN_SUBSTRINGS:
        assert secreto.lower() not in capturado.out.lower()
        assert secreto.lower() not in capturado.err.lower()
        assert secreto.lower() not in json.dumps(draft).lower()


# ---- Capa 2 (añadido): puente status "confirmed" -> confirmed=True ---------


def test_mensaje_para_smtp_lleva_confirmed_true_sin_mutar_nada(
    cli, tmp_root, capsys, monkeypatch
):
    """Integración: el mensaje entregado a send_smtp_message es una copia NUEVA
    del draft confirmado con EXACTAMENTE confirmed=True (puente
    status 'confirmed' -> confirmed=True), conservando todos los campos
    (account_id, to, subject, body, status, confirmation_hash) y SIN mutar ni
    el dict devuelto por confirm_email_draft ni el draft persistido en disco."""
    confirmada_original = {}
    _stub_backend(monkeypatch, cli)
    confirm_real = cli.confirm_email_draft

    def envoltorio_confirm(draft, frase):
        resultado = confirm_real(draft, frase)
        confirmada_original["objeto"] = resultado
        confirmada_original["copia_antes"] = copy.deepcopy(resultado)
        return resultado

    monkeypatch.setattr(cli, "confirm_email_draft", envoltorio_confirm)
    recibidos = []
    monkeypatch.setattr(
        cli,
        "send_smtp_message",
        lambda account, config, mensaje: recibidos.append(mensaje) or None,
    )

    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    capsys.readouterr()
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()

    assert rc == EXIT_OK, "el envio confirmado debe terminar en 0"
    assert len(recibidos) == 1, "send_smtp_message se invoca exactamente una vez"
    mensaje = recibidos[0]
    # el puente exacto: la clave booleana que smtp_send exige
    assert mensaje.get("confirmed") is True, (
        "el mensaje entregado a send_smtp_message debe tener confirmed is True"
    )
    assert mensaje.get("status") == "confirmed"
    # conserva TODOS los campos del draft confirmado
    for clave, valor in confirmada_original["copia_antes"].items():
        assert mensaje.get(clave) == valor, f"se perdio el campo {clave!r}"
    # copia nueva: el dict devuelto por confirm_email_draft NO se muto
    assert mensaje is not confirmada_original["objeto"], (
        "debe entregarse una copia nueva, no el retorno original"
    )
    assert "confirmed" not in confirmada_original["objeto"], (
        "el dict confirmado original no debe mutarse"
    )
    # el draft persistido tampoco se muta: sigue pending, sin clave confirmed
    draft_en_disco = json.loads(
        (tmp_root / "drafts" / (draft_id + ".json")).read_text(encoding="utf-8")
    )
    assert draft_en_disco["status"] == "pending"
    assert "confirmed" not in draft_en_disco
    # salida limpia, sin secretos
    lineas = [ln for ln in capturado.out.splitlines() if ln.strip()]
    assert lineas == [json.dumps({"id": draft_id, "status": "sent"}, sort_keys=True)]
    for bad in SECRETS_FORBIDDEN_SUBSTRINGS:
        assert bad not in capturado.out.lower()
        assert bad not in capturado.err.lower()


# ---- Capa 2 (añadido): contactos salientes post-envío ----------------------


def _draft_id_de(tmp_root):
    return next((tmp_root / "drafts").glob("*.json")).stem


def test_send_exitoso_delega_en_orden_y_llama_al_store_una_vez(
    cli, tmp_root, capsys, monkeypatch
):
    """Después de send_smtp_message exitoso (y solo entonces): delega en
    extract_outgoing_contacts(confirmed) y luego en store_email_contacts
    UNA sola vez; stdout exitoso sigue siendo exactamente una línea JSON."""
    secuencia, stores = [], []
    _stub_backend(monkeypatch, cli)
    monkeypatch.setattr(
        cli, "send_smtp_message", lambda account, config, msg: secuencia.append("smtp")
    )
    monkeypatch.setattr(
        cli,
        "extract_outgoing_contacts",
        lambda msg: secuencia.append(("extract", msg.get("to"), msg.get("status")))
        or [{"name": "A", "email": "a@b.c"}],
    )
    monkeypatch.setattr(
        cli,
        "store_email_contacts",
        lambda root, contacts: stores.append((root, contacts)) or 1,
    )
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    capsys.readouterr()
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()
    assert rc == EXIT_OK
    # orden: SMTP primero; la extraccion recibe el draft CONFIRMADO con sus To
    assert secuencia == ["smtp", ("extract", ["a@b.c"], "confirmed")]
    # UNA sola llamada al store, con el resultado de la extraccion y el ROOT
    assert stores == [(str(tmp_root), [{"name": "A", "email": "a@b.c"}])]
    lineas = [ln for ln in capturado.out.splitlines() if ln.strip()]
    assert len(lineas) == 1
    emitido = json.loads(lineas[0])
    assert set(emitido) == SENT_JSON_KEYS
    assert emitido == {"id": draft_id, "status": "sent"}
    # sin secretos en la salida
    for bad in SECRETS_FORBIDDEN_SUBSTRINGS:
        assert bad not in capturado.out.lower()
        assert bad not in capturado.err.lower()


def test_send_lista_vacia_no_es_error_y_store_una_vez(
    cli, tmp_root, capsys, monkeypatch
):
    """Lista vacía: extract -> [] NO es error; store([]) una sola vez y la
    rama sigue exitosa con su única línea JSON."""
    stores = []
    _stub_backend(monkeypatch, cli)
    monkeypatch.setattr(cli, "extract_outgoing_contacts", lambda msg: [])
    monkeypatch.setattr(
        cli,
        "store_email_contacts",
        lambda root, contacts: stores.append((root, contacts)) or 0,
    )
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    capsys.readouterr()  # descarta la salida del draft: solo evalua el send
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()
    assert rc == EXIT_OK
    assert stores == [(str(tmp_root), [])]
    lineas = [ln for ln in capturado.out.splitlines() if ln.strip()]
    assert len(lineas) == 1
    assert json.loads(lineas[0]) == {"id": draft_id, "status": "sent"}


def test_fallo_del_store_tras_smtp_devuelve_1_sin_traceback(
    cli, tmp_root, capsys, monkeypatch
):
    """Store falla tras SMTP exitoso: error genérico en stderr, código 1,
    sin traceback ni contenido de excepción cruda, y SIN línea JSON de éxito."""
    def romper(root, contacts):
        llamadas["store"] += 1
        raise RuntimeError("boom-interno-no-revelado")

    llamadas = {"smtp": 0, "extract": 0, "store": 0}
    _stub_backend(monkeypatch, cli)
    monkeypatch.setattr(
        cli, "send_smtp_message", lambda *a: llamadas.__setitem__("smtp", llamadas["smtp"] + 1)
    )
    monkeypatch.setattr(
        cli,
        "extract_outgoing_contacts",
        lambda msg: llamadas.__setitem__("extract", llamadas["extract"] + 1)
        or [{"name": "A", "email": "a@b.c"}],
    )
    monkeypatch.setattr(cli, "store_email_contacts", romper)
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()
    assert rc == EXIT_OP_ERROR
    # el envío y la extraccion SÍ ocurrieron (el fallo fue en el store)
    assert llamadas == {"smtp": 1, "extract": 1, "store": 1}
    assert "sent" not in capturado.out, "sin fallo del store no hay línea de éxito"
    assert "traceback" not in capturado.err.lower()
    assert "boom" not in capturado.err, "sin excepción cruda en stderr"
    assert capturado.err.strip() != "", "debe haber un error genérico en stderr"


def test_fallo_de_extraccion_tras_smtp_devuelve_1_sin_traceback(
    cli, tmp_root, capsys, monkeypatch
):
    """La extracción también falla genérico: código 1, sin traceback, sin
    línea de éxito y SIN ninguna llamada al store."""
    llamadas = {"extract": 0, "store": 0}
    _stub_backend(monkeypatch, cli)
    monkeypatch.setattr(cli, "send_smtp_message", lambda *a: None)
    monkeypatch.setattr(
        cli,
        "extract_outgoing_contacts",
        lambda msg: llamadas.__setitem__(
            "extract", llamadas["extract"] + 1
        )
        or (_ for _ in ()).throw(ValueError("to-invalido-no-revelado")),
    )
    monkeypatch.setattr(
        cli,
        "store_email_contacts",
        lambda root, contacts: llamadas.__setitem__("store", llamadas["store"] + 1),
    )
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    capturado = capsys.readouterr()
    assert rc == EXIT_OP_ERROR
    assert llamadas == {"extract": 1, "store": 0}
    assert "sent" not in capturado.out
    assert "traceback" not in capturado.err.lower()
    assert "no-revelado" not in capturado.err


def test_fallo_smtp_no_delega_contactos(cli, tmp_root, monkeypatch):
    """Si send_smtp_message falla, NO se extraen ni se almacenan contactos."""
    llamadas = {"smtp": 0, "extract": 0, "store": 0}
    _stub_backend(monkeypatch, cli)
    monkeypatch.setattr(
        cli,
        "send_smtp_message",
        lambda *a: llamadas.__setitem__("smtp", llamadas["smtp"] + 1)
        or (_ for _ in ()).throw(RuntimeError("smtp-no-revelado")),
    )
    monkeypatch.setattr(
        cli,
        "extract_outgoing_contacts",
        lambda msg: llamadas.__setitem__("extract", llamadas["extract"] + 1),
    )
    monkeypatch.setattr(
        cli,
        "store_email_contacts",
        lambda root, contacts: llamadas.__setitem__("store", llamadas["store"] + 1),
    )
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = _draft_id_de(tmp_root)
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, CONFIRM_PHRASE])
    assert rc == EXIT_OP_ERROR
    assert llamadas == {"smtp": 1, "extract": 0, "store": 0}
