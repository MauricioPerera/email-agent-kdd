# -*- coding: utf-8 -*-
"""Oracle independiente para store_email_contacts (contrato store-email-contacts).

No importa nada del target a nivel de modulo: todas las pruebas obtienen la
funcion via _target(), que hace importlib.import_module y pytest.skip si el
modulo o la funcion no existen todavia.
"""
import importlib
import json
import os

import pytest

TARGET_MODULE = "src.email.contact_store"
TARGET_ATTR = "store_email_contacts"

STORE_NAME = "contacts.json"

# frozen-example del contrato (una sola linea JSON + salto de linea final).
FROZEN_INPUTS = [
    {"name": "Ana Garcia", "email": "ANA@example.com"},
    {"name": "", "email": "bob@example.com"},
    {"name": "Ana Again", "email": "ana@example.com"},
]
FROZEN_BYTES = (
    '{"contacts": [{"email": "ana@example.com", "name": "Ana Garcia"},'
    ' {"email": "bob@example.com", "name": ""}]}\n'
).encode("utf-8")

INVALID_ROOTS = ["", "   ", None, 123]

INVALID_CONTACTS = [
    "not-a-list",
    [{"name": "Ana", "email": "ana@example.com", "extra": 1}],
    [{"name": "Ana"}],
    [{"name": "Ana", "email": ""}],
    [{"name": "Ana", "email": "ana example.com"}],
    [["ana@example.com"]],
]

# Intentos de path traversal via contenido de las entradas (email/name).
TRAVERSAL_CONTACTS = [
    [{"name": "Evil", "email": "../contacts@example.com"}],
    [{"name": "Evil", "email": "a/../b@example.com"}],
    [{"name": "Evil", "email": "..\\contacts@example.com"}],
    [{"name": "..\\..\\evil", "email": "ok@example.com"}],
    [{"name": "/etc/passwd", "email": "ok2@example.com"}],
]


def _target():
    """Devuelve la funcion target; pytest.skip si modulo o funcion faltan."""
    try:
        module = importlib.import_module(TARGET_MODULE)
    except ImportError:
        pytest.skip("falta el modulo %s" % TARGET_MODULE)
    fn = getattr(module, TARGET_ATTR, None)
    if fn is None or not callable(fn):
        pytest.skip("falta %s.%s" % (TARGET_MODULE, TARGET_ATTR))
    return fn


def _read_store(root):
    with open(os.path.join(str(root), STORE_NAME), "rb") as fh:
        return fh.read()


def test_frozen_example_crea_libreta_y_cuenta_nuevos(tmp_path):
    store_email_contacts = _target()
    root = tmp_path / "explicit-root"
    returned = store_email_contacts(str(root), FROZEN_INPUTS)
    assert isinstance(returned, int)
    # Los tres contactos se deduplican a dos unicos en el store.
    assert returned == 2
    raw = _read_store(root)
    assert raw == FROZEN_BYTES
    data = json.loads(raw.decode("utf-8"))
    assert set(data) == {"contacts"}
    assert data["contacts"] == [
        {"email": "ana@example.com", "name": "Ana Garcia"},
        {"email": "bob@example.com", "name": ""},
    ]
    # Orden por email ascendente y claves ordenadas en disco.
    emails = [c["email"] for c in data["contacts"]]
    assert emails == sorted(emails)
    assert list(data["contacts"][0]) == sorted(["name", "email"])


def test_deduplica_emails_ignorando_mayusculas(tmp_path):
    store_email_contacts = _target()
    root = tmp_path / "dedup-root"
    contacts = [
        {"name": "Primera", "email": "  Ana@Example.COM "},
        {"name": "Segunda", "email": "ana@example.com"},
        {"name": "Tercera", "email": "ANA@example.com"},
    ]
    assert store_email_contacts(str(root), contacts) == 1
    data = json.loads(_read_store(root).decode("utf-8"))
    assert data["contacts"] == [{"email": "ana@example.com", "name": "Primera"}]


def test_repetir_la_misma_entrada_es_idempotente(tmp_path):
    store_email_contacts = _target()
    root = tmp_path / "idem-root"
    first_return = store_email_contacts(str(root), FROZEN_INPUTS)
    first_bytes = _read_store(root)
    second_return = store_email_contacts(str(root), FROZEN_INPUTS)
    assert second_return == first_return == 2
    assert _read_store(root) == first_bytes == FROZEN_BYTES


def test_raiz_explícita_no_es_el_cwd(tmp_path):
    store_email_contacts = _target()
    cwd = os.path.realpath(os.getcwd())
    cwd_store = os.path.join(cwd, STORE_NAME)
    existed_before = os.path.exists(cwd_store)
    root = tmp_path / "explicit-no-cwd"
    store_email_contacts(str(root), FROZEN_INPUTS)
    resolved = os.path.realpath(str(root))
    assert resolved != cwd
    assert os.path.isdir(resolved)
    # El store vive dentro de la raiz explicita, no en el cwd. Si el cwd ya
    # tenia una libreta preexistente (dato real del usuario), esta NO se toca.
    assert os.path.isfile(os.path.join(resolved, STORE_NAME))
    if not existed_before:
        assert not os.path.exists(cwd_store)
    if existed_before:
        with open(cwd_store, "rb") as fh:
            preexisting = fh.read()
        with open(os.path.join(resolved, STORE_NAME), "rb") as fh:
            assert fh.read() != preexisting or str(resolved) == cwd


def test_registros_invalidos_lanzan_valueerror(tmp_path):
    store_email_contacts = _target()
    for bad_root in INVALID_ROOTS:
        with pytest.raises(ValueError):
            store_email_contacts(bad_root, [])
    for bad_contacts in INVALID_CONTACTS:
        root = tmp_path / "invalid-root"
        with pytest.raises(ValueError):
            store_email_contacts(str(root), bad_contacts)
        # Validacion antes de tocar disco: sin escrituras parciales.
        assert not os.path.exists(str(root)) or os.listdir(str(root)) == []


def test_path_traversal_rechazado(tmp_path):
    store_email_contacts = _target()
    for bad in TRAVERSAL_CONTACTS:
        root = tmp_path / "traversal-root"
        with pytest.raises(ValueError):
            store_email_contacts(str(root), bad)
        # Ninguna escritura parcial dentro de la raiz ni fuera de ella.
        if os.path.isdir(str(root)):
            assert os.listdir(str(root)) == []
        # Sin escrituras en el cwd: si ya existia una libreta preexistente en
        # el cwd (dato real del usuario), la llamada rechazada no la crea ni
        # la modifica (el mtime se conserva).
        cwd_store = os.path.join(os.path.realpath(os.getcwd()), STORE_NAME)
        existed_before = os.path.exists(cwd_store)
        if existed_before:
            mtime = os.path.getmtime(cwd_store)
        else:
            mtime = None
        assert (os.path.exists(cwd_store) and mtime is not None) == existed_before
