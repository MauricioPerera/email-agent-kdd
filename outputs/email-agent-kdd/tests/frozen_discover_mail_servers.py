"""Tests congelados del contrato discover_mail_servers.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni el target, y JAMAS
hace red ni consulta DNS real: el resolver FALSO en memoria es
obligatorio en todos los casos dinamicos. Todo offline, sin
servidores y sin credenciales.
"""

import ast
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "discover-mail-servers.md"
)

SECTIONS = [
    "Intent",
    "Interface",
    "Invariants",
    "Examples",
    "Do / Don't",
    "Tests",
    "Constraints",
]

SIGNATURE = "def discover_mail_servers(email: str, resolver=None) -> dict"

RESULT_KEYS = ("imap_host", "imap_port", "smtp_host", "smtp_port")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# Mapa de proveedores conocidos (coincidencia EXACTA del dominio).
KNOWN = {
    "gmail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "googlemail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "outlook.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "hotmail.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "live.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "msn.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
}


class FakeResolver:
    """Resolver falso en memoria con el protocolo resolver(name, rtype)."""

    def __init__(self, table=None):
        self._table = dict(table or {})
        self.calls = []

    def __call__(self, name, rtype):
        self.calls.append((name, rtype))
        return list(self._table.get((name, rtype), []))

    def table_set(self, name, rtype, records):
        self._table[(name, rtype)] = list(records)


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _body(text):
    return text.split("---\n", 2)[2]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _validate_email(email):
    """Reglas EXACTAS de validacion del correo en el contrato."""
    if not isinstance(email, str):
        raise ValueError("correo invalido")
    stripped = email.strip()
    if stripped == "" or len(stripped) > 254:
        raise ValueError("correo invalido")
    if stripped.count("@") != 1:
        raise ValueError("correo invalido")
    local, _, domain = stripped.partition("@")
    if local == "" or domain == "":
        raise ValueError("correo invalido")
    if len(domain) > 253 or DOMAIN_PATTERN.fullmatch(domain) is None:
        raise ValueError("correo invalido")
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        raise ValueError("correo invalido")
    return domain.lower()


def _valid_host(host):
    if not isinstance(host, str) or host == "" or len(host) > 253:
        return False
    if ".." in host:
        return False
    return HOST_PATTERN.fullmatch(host) is not None


def _pick_srv(records):
    """Menor prioridad; empate: el primero en el orden devuelto."""
    best = None
    for record in records:
        if not isinstance(record, str):
            continue
        parts = record.split(" ")
        if len(parts) != 4:
            continue
        try:
            priority = int(parts[0])
            port = int(parts[2])
        except ValueError:
            continue
        if priority < 0 or not 1 <= port <= 65535:
            continue
        target = parts[3].strip().rstrip(".").lower()
        if target in ("", ".") or not _valid_host(target):
            continue
        if best is None or priority < best[0]:
            best = (priority, target, port)
    if best is None:
        return None
    return (best[1], best[2])


class _Queries:
    """Consulta con cache: cada (name, rtype) como maximo una vez."""

    def __init__(self, resolver, log):
        self._resolver = resolver
        self._log = log
        self._seen = {}

    def ask(self, name, rtype):
        key = (name, rtype)
        if key not in self._seen:
            self._seen[key] = self._resolver(name, rtype)
            self._log.append(key)
        return self._seen[key]


def _discover_model(email, resolver=None, log=None):
    """Modelo de referencia con el orden EXACTO del contrato.

    El oracle no abre red: con resolver=None solo aplica el mapa
    conocido (los candidatos requieren un resolver inyectado).
    """
    if log is None:
        log = []
    domain = _validate_email(email)
    queries = _Queries(resolver, log) if resolver is not None else None

    def ask(name, rtype):
        if queries is None:
            return []
        return queries.ask(name, rtype)

    imap = _pick_srv(ask("_imaps._tcp." + domain, "SRV"))
    smtp = _pick_srv(ask("_submissions._tcp." + domain, "SRV"))
    if smtp is None:
        smtp = _pick_srv(ask("_submission._tcp." + domain, "SRV"))
    if imap is None and domain in KNOWN:
        imap = (KNOWN[domain][0], KNOWN[domain][1])
    if smtp is None and domain in KNOWN:
        smtp = (KNOWN[domain][2], KNOWN[domain][3])

    if imap is None:
        for candidate in ("imap." + domain, "mail." + domain):
            if ask(candidate, "A"):
                imap = (candidate, 993)
                break
    if smtp is None:
        for candidate in ("smtp." + domain, "mail." + domain):
            if ask(candidate, "A"):
                smtp = (candidate, 587)
                break
    if imap is None or smtp is None:
        raise ValueError("no se pudieron descubrir los servidores de correo")
    return {
        "imap_host": imap[0],
        "imap_port": int(imap[1]),
        "smtp_host": smtp[0],
        "smtp_port": int(smtp[1]),
    }


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: discover_mail_servers" in front
    assert 'signature: "' + SIGNATURE + '"' in front
    assert "target: src/email/discover_mail_servers.py" in front
    assert "tests: tests/frozen_discover_mail_servers.py" in front
    assert "params_max: 2" in front, "budget sin params_max: 2"
    assert "deps_allowed: []" in front, "deps_allowed no es vacia"
    for forbidden in ("subprocess", "print", "open", "smtplib", "imaplib", "urllib", "requests"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert "resolver(name" in body, "el contrato no documenta el protocolo del resolver"
    assert "SRV" in body, "el contrato no documenta SRV"
    for srv in ("_imaps._tcp", "_submissions._tcp", "_submission._tcp"):
        assert srv in body, "el contrato sin el servicio " + srv
    assert "imap.gmail.com" in body and "smtp.gmail.com" in body, "sin mapa Gmail"
    assert "outlook.office365.com" in body, "sin mapa Outlook"
    assert "imap.<dominio>" in body and "mail.<dominio>" in body, "sin candidatos IMAP"
    assert "smtp.<dominio>" in body, "sin candidatos SMTP"
    assert "getaddrinfo" in body, "el contrato no documenta el backend real"
    assert "Existencia DNS no es soporte" in body, "sin regla existencia != soporte"
    assert "heuristic" in body, "sin prohibicion de heuristica silenciosa"
    assert "ValueError" in body, "faltan los errores documentados"
    assert "993" in body and "587" in body, "faltan los puertos documentados"
    assert "credencial" in body or "secretos" in body, "sin regla de credenciales"
    assert "resolv" in body or "resolver" in body, "sin rol del resolver"


def test_contract_frozen_inputs():
    inputs = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    expected = json.loads(_fenced_block(_contract_text(), "frozen-example"))
    result = _discover_model(inputs["email"], None)
    assert result == expected, "el modelo no reproduce el ejemplo frozen"
    assert set(result) == set(RESULT_KEYS)


def test_gmail_normalizes_email_case_and_spaces():
    result = _discover_model("  Ana.Gomez@GMAIL.COM  ", None)
    assert result == {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
    }
    assert all(isinstance(result[key], int) for key in ("imap_port", "smtp_port"))


def test_own_domain_candidates_confirmed():
    resolver = FakeResolver(
        {
            ("imap.midominio.com", "A"): ["203.0.113.7"],
            ("smtp.midominio.com", "A"): ["203.0.113.8"],
        }
    )
    result = _discover_model("usuario@midominio.com", resolver)
    assert result == {
        "imap_host": "imap.midominio.com",
        "imap_port": 993,
        "smtp_host": "smtp.midominio.com",
        "smtp_port": 587,
    }


def test_mail_candidate_fallback():
    resolver = FakeResolver(
        {
            ("mail.midominio.com", "A"): ["203.0.113.9"],
        }
    )
    result = _discover_model("usuario@midominio.com", resolver)
    assert result == {
        "imap_host": "mail.midominio.com",
        "imap_port": 993,
        "smtp_host": "mail.midominio.com",
        "smtp_port": 587,
    }


def test_srv_wins_over_known_map():
    resolver = FakeResolver(
        {
            ("_imaps._tcp.gmail.com", "SRV"): ["10 5 9993 imap-fake.gmail.com."],
            ("_submissions._tcp.gmail.com", "SRV"): ["10 5 5946 smtp-fake.gmail.com."],
        }
    )
    result = _discover_model("ana@gmail.com", resolver)
    assert result == {
        "imap_host": "imap-fake.gmail.com",
        "imap_port": 9993,
        "smtp_host": "smtp-fake.gmail.com",
        "smtp_port": 5946,
    }


def test_srv_priority_and_case_insensitive_target():
    resolver = FakeResolver(
        {
            ("_imaps._tcp.midominio.com", "SRV"): [
                "20 5 993 host-b.midominio.com",
                "10 5 993 host-a.midominio.com.",
            ],
            ("smtp.midominio.com", "A"): ["203.0.113.8"],
        }
    )
    result = _discover_model("usuario@MIDOMINIO.com", resolver)
    assert result["imap_host"] == "host-a.midominio.com", "no gana la menor prioridad"
    assert result["imap_port"] == 993
    assert result["smtp_host"] == "smtp.midominio.com"


def test_malformed_srv_records_are_ignored():
    resolver = FakeResolver(
        {
            ("_imaps._tcp.midominio.com", "SRV"): [
                "10 5 993",
                "10 5 no-es-puerto imap.midominio.com",
                "10 5 70000 imap.midominio.com",
                "10 5 993 .",
                "10 5 993 bad host",
                7,
                "10 5 993 imap.midominio.com",
            ],
            ("imap.midominio.com", "A"): ["203.0.113.7"],
            ("smtp.midominio.com", "A"): ["203.0.113.8"],
        }
    )
    result = _discover_model("usuario@midominio.com", resolver)
    assert result["imap_host"] == "imap.midominio.com"
    assert result["imap_port"] == 993


def test_incomplete_confidence_raises_value_error():
    resolver = FakeResolver({})
    try:
        _discover_model("usuario@midominio.com", resolver)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("descubrimiento incompleto aceptado como parcial")
    assert resolver.calls, "el resolver no fue consultado"


def test_one_side_unconfirmed_raises_value_error():
    # IMAP confirma pero SMTP no: JAMAS retorno parcial.
    resolver = FakeResolver({("imap.midominio.com", "A"): ["203.0.113.7"]})
    try:
        _discover_model("usuario@midominio.com", resolver)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("un solo flujo confirmado devolvio resultado")


def test_invalid_email_rejects_before_any_query():
    bad_emails = [
        "",
        "   ",
        "\t",
        None,
        7,
        b"x",
        "sin-arroba",
        "a@@b.com",
        "a@ b.com",
        "a@.com",
        "a@com.",
        "a@com..com",
        "@x.com",
        "x@",
        "a@" + "d" * 250 + ".com",
    ]
    resolver = FakeResolver({("_imaps._tcp.com", "SRV"): ["1 1 993 x.com"]})
    for email in bad_emails:
        try:
            _discover_model(email, resolver)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("correo invalido aceptado: %r" % (email,))
    assert resolver.calls == [], "correo invalido disparo una consulta"


def test_determinism_and_no_duplicate_queries():
    domain = "usuario@midominio.com"
    table = {
        ("imap.midominio.com", "A"): ["203.0.113.7"],
        ("smtp.midominio.com", "A"): ["203.0.113.8"],
        ("mail.midominio.com", "A"): ["203.0.113.9"],
    }
    first_log, second_log = [], []
    first = _discover_model(domain, FakeResolver(table), first_log)
    second = _discover_model(domain, FakeResolver(table), second_log)
    assert first == second and first is not second, "determinismo roto"
    assert first_log == second_log, "el orden de consultas no es fijo"
    assert len(first_log) == len(set(first_log)), "consultas duplicadas de (name, rtype)"


def test_result_shape_exact_keys():
    result = _discover_model("ana@gmail.com", None)
    assert set(result) == set(RESULT_KEYS), "el retorno no tiene exactamente 4 claves"
    for key in RESULT_KEYS:
        assert isinstance(result[key], str) if key.endswith("_host") else isinstance(result[key], int)
    assert result == json.loads(json.dumps(result)), "el retorno no es serializable"


def test_models_have_no_side_channels():
    """El modelo de discovery no imprime, abre archivos ni lanza procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    func = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_discover_model"
    )
    calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
    names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
    for banned in ("print", "open", "system", "Popen", "environ", "getaddrinfo"):
        assert banned not in names, "el modelo usa un canal de escape: " + banned
    for banned in ("socket", "subprocess", "smtplib", "imaplib", "urllib"):
        assert banned not in ast.dump(func), "el modelo referencia " + banned


def test_resolver_is_the_only_dns_path_in_oracle():
    """El oracle jamas consulta DNS real: solo el resolver falso."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    for banned in ("socket", "dns", "dnspython", "resolv", "requests"):
        assert banned not in imported, "el oracle importa " + banned