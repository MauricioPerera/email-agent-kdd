"""Diagnostico local y de solo lectura para preparar el primer uso."""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

LANGUAGES = {"es", "en", "pt"}

_LABELS = {
    "es": {"title": "Diagnóstico de Email Agent", "status": "Estado", "checks": "Comprobaciones", "next": "Siguiente paso", "ready": "Listo", "needs_attention": "Requiere atención", "ok": "Correcto", "warning": "Advertencia", "error": "Error", "yes": "sí", "no": "no"},
    "en": {"title": "Email Agent diagnostics", "status": "Status", "checks": "Checks", "next": "Next step", "ready": "Ready", "needs_attention": "Needs attention", "ok": "OK", "warning": "Warning", "error": "Error", "yes": "yes", "no": "no"},
    "pt": {"title": "Diagnóstico do Email Agent", "status": "Status", "checks": "Verificações", "next": "Próximo passo", "ready": "Pronto", "needs_attention": "Requer atenção", "ok": "Correto", "warning": "Aviso", "error": "Erro", "yes": "sim", "no": "não"},
}

_DETAILS = {
    "platform": {"ok": {"es": "sistema operativo soportado", "en": "supported operating system", "pt": "sistema operacional compatível"}, "error": {"es": "sistema operativo sin almacén nativo soportado", "en": "operating system has no supported native store", "pt": "sistema operacional sem armazenamento nativo compatível"}},
    "python": {"ok": {"es": "Python 3.10 o superior", "en": "Python 3.10 or newer", "pt": "Python 3.10 ou superior"}, "error": {"es": "se requiere Python 3.10 o superior", "en": "Python 3.10 or newer is required", "pt": "é necessário Python 3.10 ou superior"}},
    "pip": {"ok": {"es": "pip disponible", "en": "pip available", "pt": "pip disponível"}, "error": {"es": "pip no está disponible para este Python", "en": "pip is not available for this Python", "pt": "pip não está disponível para este Python"}},
    "gui": {"ok": {"es": "formulario gráfico disponible", "en": "graphical form available", "pt": "formulário gráfico disponível"}, "warning": {"es": "Tkinter no está disponible; se puede usar el asistente de terminal", "en": "Tkinter is unavailable; the terminal wizard can be used", "pt": "Tkinter não está disponível; o assistente de terminal pode ser usado"}},
    "credential_manager": {"ok": {"es": "Credential Manager se comprobará al guardar la cuenta", "en": "Credential Manager will be checked when saving the account", "pt": "o Credential Manager será verificado ao salvar a conta"}},
    "keychain": {"ok": {"es": "Keychain disponible", "en": "Keychain available", "pt": "Keychain disponível"}, "error": {"es": "falta el comando security", "en": "the security command is missing", "pt": "o comando security está ausente"}},
    "secretservice": {"ok": {"es": "Secret Service disponible", "en": "Secret Service available", "pt": "Secret Service disponível"}, "error": {"es": "falta secret-tool; se requiere libsecret y una sesión de escritorio", "en": "secret-tool is missing; libsecret and a desktop session are required", "pt": "secret-tool está ausente; libsecret e uma sessão de desktop são necessárias"}},
}


def _check(name, status, detail, required=True):
    return {"name": name, "status": status, "detail": detail, "required": required}


def run_diagnostics(root=None, repair=False):
    """Devuelve checks seguros sin red, credenciales ni escrituras.

    Con ``repair=True`` añade instrucciones de reparación; nunca las ejecuta.
    """
    checks = []
    supported = sys.platform == "win32" or sys.platform == "darwin" or sys.platform.startswith("linux")
    checks.append(_check(
        "platform",
        "ok" if supported else "error",
        "sistema operativo soportado" if supported else "sistema operativo sin almacén nativo soportado",
    ))
    version_ok = sys.version_info >= (3, 10)
    checks.append(_check(
        "python",
        "ok" if version_ok else "error",
        "Python 3.10 o superior" if version_ok else "se requiere Python 3.10 o superior",
    ))
    pip_ok = importlib.util.find_spec("pip") is not None
    checks.append(_check(
        "pip",
        "ok" if pip_ok else "error",
        "pip disponible" if pip_ok else "pip no está disponible para este Python",
    ))
    tkinter_ok = importlib.util.find_spec("tkinter") is not None
    checks.append(_check(
        "gui",
        "ok" if tkinter_ok else "warning",
        "formulario gráfico disponible" if tkinter_ok else "Tkinter no está disponible; se puede usar el asistente de terminal",
        required=False,
    ))
    if sys.platform == "darwin":
        native_ok, detail = shutil.which("security") is not None, "Keychain disponible" if shutil.which("security") else "falta el comando security"
        native_name = "keychain"
    elif sys.platform.startswith("linux"):
        native_ok, detail = shutil.which("secret-tool") is not None, "Secret Service disponible" if shutil.which("secret-tool") else "falta secret-tool; se requiere libsecret y una sesión de escritorio"
        native_name = "secretservice"
    elif sys.platform == "win32":
        native_ok, detail, native_name = True, "Credential Manager se comprobará al guardar la cuenta", "credential_manager"
    else:
        native_ok, detail, native_name = False, "no hay almacén nativo soportado", "native_store"
    checks.append(_check(native_name, "ok" if native_ok else "error", detail))
    if root is not None:
        root_ok = isinstance(root, str) and bool(root.strip()) and Path(root).is_dir()
        checks.append(_check("root", "ok" if root_ok else "warning", "carpeta local accesible" if root_ok else "la carpeta indicada no existe; se creará durante la configuración", required=False))
    required_errors = [item for item in checks if item["required"] and item["status"] == "error"]
    actions = []
    if repair:
        if not version_ok:
            actions.append("Instala Python 3.10 o superior y vuelve a abrir la terminal")
        if not pip_ok:
            actions.append("Repara pip desde la instalación de Python; no uses un pip de otra versión")
        if not tkinter_ok:
            actions.append("Instala el componente Tkinter de tu distribución o usa account setup en terminal")
        if not native_ok:
            if native_name == "keychain":
                actions.append("Verifica que macOS incluya el comando security y que Keychain esté disponible")
            elif native_name == "secretservice":
                actions.append("Instala libsecret/secret-tool e inicia una sesión de escritorio con Secret Service")
            else:
                actions.append("Usa Windows, macOS o Linux con su almacén seguro nativo compatible")
        if not actions:
            actions.append("No hay reparaciones pendientes; puedes abrir el formulario de configuración")
    result = {
        "status": "ready" if not required_errors else "needs_attention",
        "checks": checks,
        "next": "Puedes abrir account setup-gui o account setup" if not required_errors else "Corrige los checks marcados como error y vuelve a ejecutar doctor",
    }
    if repair:
        result["repair"] = {"performed": False, "actions": actions}
    return result


def write_diagnostic_report(path, result):
    """Escribe un reporte local y atómico sin incluir un ROOT ni secretos."""
    return _write_diagnostic_report(path, result, "es", "json")


def _localized_detail(item, language):
    return _DETAILS.get(item["name"], {}).get(item["status"], {}).get(language, item["detail"])


def _write_diagnostic_report(path, result, language, report_format):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("ruta de reporte invalida")
    target = Path(path)
    if target.name in {"", ".", ".."}:
        raise ValueError("ruta de reporte invalida")
    if language not in LANGUAGES:
        raise ValueError("idioma invalido")
    if report_format not in {"json", "text"}:
        raise ValueError("formato invalido")
    labels = _LABELS[language]
    localized_checks = [
        {**{key: item[key] for key in ("name", "status", "required")}, "detail": _localized_detail(item, language)}
        for item in result.get("checks", [])
    ]
    next_step = result.get("next")
    if language == "en":
        next_step = "You can open account setup-gui or account setup" if result.get("status") == "ready" else "Fix the checks marked as errors and run doctor again"
    elif language == "pt":
        next_step = "Você pode abrir account setup-gui ou account setup" if result.get("status") == "ready" else "Corrija as verificações marcadas como erro e execute doctor novamente"
    safe = {
        "language": language,
        "status": result.get("status"),
        "checks": localized_checks,
        "next": next_step,
    }
    if "repair" in result:
        safe["repair"] = {
            "performed": False,
            "actions": list(result["repair"].get("actions", [])),
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        if report_format == "json":
            output = json.dumps(safe, ensure_ascii=False, indent=2) + "\n"
        else:
            lines = [labels["title"], "=" * len(labels["title"]), "", f"{labels['status']}: {labels[safe['status']]}", "", f"{labels['checks']}:"]
            lines.extend(f"- {item['name']}: {labels[item['status']]} — {item['detail']}" for item in localized_checks)
            lines.extend(["", f"{labels['next']}: {safe['next']}"])
            output = "\n".join(lines) + "\n"
        temporary.write_text(output, encoding="utf-8")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return True
