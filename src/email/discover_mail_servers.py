"""Descubre los servidores IMAP/SMTP de un dominio propio desde el correo del usuario.

Orden fijo: SRV seguro (_imaps, _submissions/_submission) por prioridad, mapa
exacto de proveedores conocidos y candidatos del dominio confirmados por el
resolver (o, con resolver=None, por socket.getaddrinfo solo para candidatos).
Jamas recibe credenciales ni secretos: discovery puro por DNS publicado.
"""

import re
import socket

_DOMAIN = re.compile(r"^[A-Za-z0-9._-]+$")
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
_KNOWN = {
    "gmail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "googlemail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "outlook.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "hotmail.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "live.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "msn.com": ("outlook.office365.com", 993, "smtp.office365.com", 587),
}


def _domain_of(email):
    """Valida el correo crudo y devuelve el dominio normalizado en minusculas."""
    if not isinstance(email, str):
        raise ValueError("correo invalido")
    stripped = email.strip()
    if not stripped or len(stripped) > 254 or stripped.count("@") != 1:
        raise ValueError("correo invalido")
    local, _, domain = stripped.partition("@")
    if (not local or not domain or len(domain) > 253
            or _DOMAIN.fullmatch(domain) is None
            or domain.startswith(".") or domain.endswith(".") or ".." in domain):
        raise ValueError("correo invalido")
    return domain.lower()


def _valid_host(host):
    return (isinstance(host, str) and host != "" and len(host) <= 253
            and ".." not in host and _HOST.fullmatch(host) is not None)


def _pick_srv(records):
    """Elige el registro de menor prioridad; empate: el primero. Invalidos: ignorados."""
    best = None
    for record in records:
        parts = record.split(" ") if isinstance(record, str) else []
        if len(parts) != 4:
            continue
        try:
            priority, port = int(parts[0]), int(parts[2])
        except ValueError:
            continue
        target = parts[3].strip().rstrip(".").lower()
        if priority < 0 or not 1 <= port <= 65535 or not _valid_host(target):
            continue
        if best is None or priority < best[0]:
            best = (priority, target, port)
    if best is None:
        return None
    return best[1], best[2]


def _query_once(resolver):
    """Consultas con cache: cada (name, rtype) como maximo una vez."""
    seen = {}

    def ask(name, rtype):
        if (name, rtype) not in seen:
            seen[(name, rtype)] = resolver(name, rtype)
        return seen[(name, rtype)]

    return ask


def _unresolved(name, rtype):
    """Sin resolver inyectado no hay SRV: getaddrinfo no lee registros SRV."""
    return []


def _confirmed(ask, host, resolver):
    """El dominio publica el host: registro A no vacio por el resolver inyectado."""
    if resolver is not None:
        return bool(ask(host, "A"))
    try:
        return bool(socket.getaddrinfo(host, None))
    except OSError:
        return False


def _srv_flow(ask, domain):
    """Paso 1 y 2 del orden fijo: SRV seguro y mapa de proveedores conocidos."""
    imap = _pick_srv(ask("_imaps._tcp." + domain, "SRV"))
    smtp = _pick_srv(ask("_submissions._tcp." + domain, "SRV"))
    if smtp is None:
        smtp = _pick_srv(ask("_submission._tcp." + domain, "SRV"))
    known = _KNOWN.get(domain)
    if known:
        imap = imap if imap is not None else (known[0], known[1])
        smtp = smtp if smtp is not None else (known[2], known[3])
    return imap, smtp


def _candidate(ask, prefix, domain, port, resolver):
    """Candidatos comunes en orden fijo; el primero que el resolver confirma."""
    for cand in (prefix + domain, "mail." + domain):
        if _confirmed(ask, cand, resolver):
            return cand, port
    return None


def discover_mail_servers(email: str, resolver=None) -> dict:
    """Descubre IMAP/SMTP del dominio propio; ValueError si algo no se confirma."""
    domain = _domain_of(email)
    ask = _query_once(resolver) if resolver is not None else _unresolved
    imap, smtp = _srv_flow(ask, domain)
    if imap is None:
        imap = _candidate(ask, "imap.", domain, 993, resolver)
    if smtp is None:
        smtp = _candidate(ask, "smtp.", domain, 587, resolver)
    if imap is None or smtp is None:
        raise ValueError("no se pudieron descubrir los servidores de correo")
    return {
        "imap_host": imap[0],
        "imap_port": int(imap[1]),
        "smtp_host": smtp[0],
        "smtp_port": int(smtp[1]),
    }