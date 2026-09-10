# -*- coding: utf-8 -*-
"""Libreta de contactos deduplicada y determinista bajo una raiz explicita.

Variante de ``account_store`` sin dependencia del directorio de trabajo: el
store vive en ``<root>/contacts.json`` (raiz recibida por parametro) y la
deduplicacion es por email normalizado. Sin red ni procesos.
"""
import json
import os
from pathlib import Path

STORE_NAME = "contacts.json"


def _validate_contact(entry):
    """Valida el esquema exacto y devuelve el contacto normalizado."""
    if not isinstance(entry, dict) or set(entry) != {"name", "email"}:
        raise ValueError("contacto invalido: se esperan las claves name y email")
    name, email = entry["name"], entry["email"]
    if not isinstance(name, str) or "/" in name or "\\" in name:
        raise ValueError("nombre de contacto invalido")
    if not isinstance(email, str):
        raise ValueError("email de contacto invalido")
    clean = email.strip()
    bad_chars = [ch for ch in clean if ch.isspace() or ord(ch) < 32]
    if not clean or bad_chars or clean.count("@") != 1:
        raise ValueError("email de contacto invalido")
    local, domain = clean.split("@")
    if not local or not domain or "/" in clean or "\\" in clean:
        raise ValueError("email de contacto invalido")
    return {"name": name, "email": clean.lower()}


def _load_store(store_root):
    """Lee las entradas guardadas; store corrupto => RuntimeError."""
    path = store_root / STORE_NAME
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data["contacts"]
        if not isinstance(data, dict) or set(data) != {"contacts"}:
            raise ValueError("estructura inesperada")
        if not isinstance(entries, list):
            raise ValueError("lista de contactos inesperada")
        return [_validate_contact(entry) for entry in entries]
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError):
        raise RuntimeError("store de contactos corrupto")


def store_email_contacts(root: str, contacts: list) -> int:
    """Fusiona ``contacts`` en ``<root>/contacts.json`` y devuelve el total."""
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser un str no vacio")
    if not isinstance(contacts, list):
        raise ValueError("contacts debe ser una lista")
    incoming = [_validate_contact(entry) for entry in contacts]
    store_root = Path(root.strip()).resolve()
    existing = _load_store(store_root)
    merged = {}
    for entry in existing + incoming:
        merged.setdefault(entry["email"], entry)
    ordered = [merged[email] for email in sorted(merged)]
    payload = json.dumps({"contacts": ordered}, sort_keys=True, ensure_ascii=False) + "\n"
    store_root.mkdir(parents=True, exist_ok=True)
    tmp_path = store_root / (STORE_NAME + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)
        os.replace(tmp_path, store_root / STORE_NAME)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return len(ordered)


def load_email_contacts(root: str) -> list:
    """Devuelve los contactos guardados en ``<root>/contacts.json`` sin escribir."""
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser un str no vacio")
    store_root = Path(root.strip()).resolve()
    return _load_store(store_root)