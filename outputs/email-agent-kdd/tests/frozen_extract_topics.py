# Oracle pytest independiente para el contrato knowledge/contracts/extract-topics.md.
# NO importa nada del target en las verificaciones estáticas; el comportamiento
# hace skip si src.email.topics.extract_topics aún no existe.
# Se ejecuta desde la raíz del proyecto (python -m pytest outputs/email-agent-kdd/tests/frozen_extract_topics.py).

import ast
import pathlib
import re

import pytest

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[1] / "knowledge" / "contracts" / "extract-topics.md"
TARGET_REL = "src/email/topics.py"
TARGET_PATH = pathlib.Path(__file__).resolve().parents[3] / "src" / "email" / "topics.py"

STOPWORDS = frozenset({
    "de", "la", "el", "los", "las", "del", "al", "a", "y", "o", "en", "con",
    "para", "por", "que", "se", "su", "sus", "lo", "un", "una", "es", "no",
    "sobre", "re", "rv", "fw", "fwd",
    "the", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "it", "this", "that",
})


def _load_target():
    """Devuelve extract_topics o None si el módulo/función aún no existe."""
    if not TARGET_PATH.exists():
        return None
    try:
        from src.email import topics as _mod
    except Exception:
        return None
    fn = getattr(_mod, "extract_topics", None)
    if not callable(fn):
        return None
    return fn


# ---------------------------------------------------------------------------
# 1. Contrato: front-matter, target/firma, siete secciones y PARAR
# ---------------------------------------------------------------------------

def _contract_text():
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_contrato_frontmatter():
    text = _contract_text()
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    required = ["task:", "intent:", "target:", "signature:", "language:",
                "budget:", "tests_frozen:", "stop_rule:"]
    for key in required:
        assert key in fm, f"falta clave de front-matter: {key}"
    assert "task: extract-topics" in fm
    assert "language: python" in fm
    assert "tests_frozen: true" in fm
    # budget con topes firmados
    assert re.search(r"max_cyclomatic:\s*\d+", fm)
    assert re.search(r"max_nesting:\s*\d+", fm)
    assert re.search(r"max_length:\s*\d+", fm)


def test_contrato_target_y_firma():
    fm = _contract_text().split("---", 2)[1]
    m = re.search(r"target:\s*(\S+)", fm)
    assert m and m.group(1) == "../../../../src/email/topics.py"
    resolved = (CONTRACT_PATH.parent / m.group(1)).resolve()
    assert resolved == TARGET_PATH
    m = re.search(r'signature:\s*"([^"]+)"', fm)
    assert m, "signature debe estar entre comillas"
    sig = m.group(1)
    assert sig == "def extract_topics(record: dict) -> list[str]"
    # la firma debe ser parseable como def aislado (sin cuerpo, se añade ':')
    ast.parse(sig + ":\n    pass")
    # y la implementación (si existe) coincide con la firma esperada
    fn = _load_target()
    if fn is None:
        pytest.skip("src.email.topics.extract_topics no existe aún")
    src = TARGET_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "extract_topics"]
    assert defs, "no se encontró def extract_topics en el target"
    args = defs[0].args
    names = [a.arg for a in getattr(args, "posonlyargs", [])] + [a.arg for a in args.args]
    assert names == ["record"], f"firma implementada: {names}"


def test_contrato_siete_secciones():
    text = _contract_text()
    for section in ["## Intent", "## Interface", "## Invariants", "## Examples",
                    "## Do / Don't", "## Tests", "## Constraints"]:
        assert section in text, f"falta sección: {section}"


def test_contrato_parar_y_reportar():
    text = _contract_text()
    fm = text.split("---", 2)[1]
    assert "PARAR y reportar" in fm, "stop_rule debe decir 'PARAR y reportar'"
    for motivo in ["body", "red", "modelo", "mutar"]:
        assert motivo in fm, f"stop_rule sin motivo: {motivo}"
    constraints = text.split("## Constraints")[1]
    assert "PARAR y reportar" in constraints, "Constraints debe repetir PARAR y reportar"
    for motivo in ["body", "mutar", "dependencias externas", "red", "modelo", "12"]:
        assert motivo in constraints, f"Constraints sin motivo: {motivo}"


# ---------------------------------------------------------------------------
# 2. Comportamiento (skip si el target no existe)
# ---------------------------------------------------------------------------

def _target():
    fn = _load_target()
    if fn is None:
        pytest.skip("src.email.topics.extract_topics no existe aún")
    return fn


def test_prefijos_re_fwd_rv_repetidos():
    extract_topics = _target()
    assert extract_topics({"subject": "Re: Re: Factura 123"}) == ["123", "factura"]
    assert extract_topics({"subject": "FWD: Informe trimestral Q3"}) == ["informe", "q3", "trimestral"]
    assert extract_topics({"subject": "Rv: RV: rv: Presupuesto final"}) == ["final", "presupuesto"]
    assert extract_topics({"subject": "Re: RE: Fwd: Re: Oferta de trabajo"}) == ["oferta", "trabajo"]


def test_casefold():
    extract_topics = _target()
    assert extract_topics({"subject": "Café y AÑO nuevo"}) == ["año", "café", "nuevo"]
    assert extract_topics({"subject": "REPORTE Final DE VENTAS"}) == ["final", "reporte", "ventas"]
    out = extract_topics({"subject": "MiXeD Case ToKeNs"})
    assert out == sorted(out)
    assert all(t == t.casefold() for t in out)


def test_stopwords():
    extract_topics = _target()
    # español
    assert extract_topics({"subject": "oferta de trabajo para el equipo"}) == ["equipo", "oferta", "trabajo"]
    # inglés
    assert extract_topics({"subject": "The report is on the desk"}) == ["desk", "report"]
    # prefijos sueltos como tokens
    assert extract_topics({"subject": "re fw fwd nota"}) == ["nota"]
    # todo stopwords -> vacío
    assert extract_topics({"subject": "la de el y o"}) == []


def test_dedupe_y_orden():
    extract_topics = _target()
    assert extract_topics({"subject": "dato dato DATO Dato reporte"}) == ["dato", "reporte"]
    out = extract_topics({"subject": "zeta alfa zeta ALFA medio"})
    assert out == sorted(out)
    assert len(set(out)) == len(out)
    assert out == ["alfa", "medio", "zeta"]


def test_maximo_doce():
    extract_topics = _target()
    subject = " ".join(f"tema{i:02d}" for i in range(20))
    out = extract_topics({"subject": subject})
    assert len(out) == 12
    assert out == sorted(out)
    assert out == [f"tema{i:02d}" for i in range(12)]


def test_solo_subject_no_body():
    extract_topics = _target()
    record = {
        "subject": "Re: Hola",
        "body": "SECRETO en el cuerpo",
        "text": "otro secreto",
        "html": "<p>mas secreto</p>",
    }
    out = extract_topics(record)
    assert out == ["hola"]
    assert all("secr" not in t and "cuerpo" not in t for t in out)
    # body con tokens no puede aparecer jamás en la salida
    r2 = {"subject": "limpio", "body": "fuga filtrada"}
    assert extract_topics(r2) == ["limpio"]
    assert "fuga" not in extract_topics(r2) and "filtrada" not in extract_topics(r2)


def test_record_sin_subject():
    extract_topics = _target()
    assert extract_topics({}) == []
    assert extract_topics({"body": "solo cuerpo"}) == []
    for bad in [None, 12345, ["x"], {"k": "v"}]:
        assert extract_topics({"subject": bad}) == []
    assert extract_topics({"subject": ""}) == []


def test_no_muta_record():
    extract_topics = _target()
    record = {"subject": "Re: Hola", "body": "SECRETO"}
    before = dict(record)
    out = extract_topics(record)
    assert record == before
    assert "subject" in record and "body" in record
    assert out == ["hola"]


def test_determinismo():
    extract_topics = _target()
    record = {"subject": "Re: Contrato y Plazo de entrega"}
    expected = ["contrato", "entrega", "plazo"]
    first = extract_topics(record)
    for _ in range(5):
        assert extract_topics(record) == first
    assert first == expected


def test_propiedad_cota_unicidad_orden():
    extract_topics = _target()
    subjects = [
        "a b c d e f g h i j k l m n o p",
        "uno",
        "Re: dos tres",
        "Presupuesto-v2 y entrega!!",
        "id-123 v1.2 separados",
    ]
    for subject in subjects:
        out = extract_topics({"subject": subject})
        assert isinstance(out, list)
        assert all(isinstance(t, str) for t in out)
        assert len(out) <= 12
        assert out == sorted(out)
        assert len(set(out)) == len(out)
        assert all(t != "" for t in out)