"""Aprobacion grafica local y determinista para enviar un borrador."""

import json
import os

from src.email.draft import create_email_draft

_ATTACHMENT_KEYS = ("attachments", "attachment", "files", "file")
_TEXT = {
    "es": {"title": "Confirmar envio de correo", "heading": "Revisa antes de enviar", "warning": "Esta accion enviara un correo real. Comprueba todos los datos.", "account": "Cuenta", "to": "Para", "subject": "Asunto", "body": "Mensaje", "check": "He revisado destinatarios, asunto y mensaje", "send": "Enviar correo ahora", "cancel": "Cancelar, no enviar"},
    "en": {"title": "Confirm email delivery", "heading": "Review before sending", "warning": "This action will send a real email. Check every field.", "account": "Account", "to": "To", "subject": "Subject", "body": "Message", "check": "I reviewed recipients, subject, and message", "send": "Send email now", "cancel": "Cancel, do not send"},
    "pt": {"title": "Confirmar envio de email", "heading": "Revise antes de enviar", "warning": "Esta acao enviara um email real. Confira todos os dados.", "account": "Conta", "to": "Para", "subject": "Assunto", "body": "Mensagem", "check": "Revisei destinatarios, assunto e mensagem", "send": "Enviar email agora", "cancel": "Cancelar, nao enviar"},
}


def load_send_preview(root: str, account_id: str, draft_id: str) -> dict:
    """Carga y valida los campos exactos que se mostraran al usuario."""
    if len(draft_id) != 64 or any(
        char not in "0123456789abcdef" for char in draft_id.lower()
    ):
        raise ValueError("invalid draft id")
    try:
        with open(os.path.join(root, "drafts", draft_id + ".json"), encoding="utf-8") as handle:
            draft = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError("unreadable draft") from exc
    if not isinstance(draft, dict) or draft.get("account_id") != account_id:
        raise ValueError("draft account mismatch")
    try:
        integrity_id = create_email_draft(
            draft["account_id"], draft["to"], draft["subject"], draft["body"]
        )["id"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid draft") from exc
    if draft.get("id") != integrity_id or draft_id != integrity_id:
        raise ValueError("draft integrity mismatch")
    if any(draft.get(key) for key in _ATTACHMENT_KEYS):
        raise ValueError("attachments unsupported")
    return {"id": draft_id, "account_id": account_id, "to": list(draft["to"]), "subject": draft["subject"], "body": draft["body"]}


class _SendApprovalForm:
    """Dialogo modal con cancelacion segura y confirmacion de dos pasos."""

    def __init__(self, master, preview: dict, language="es"):
        self.window = master
        self.preview = preview
        self.language = language if language in _TEXT else "es"
        self.approved = False

    def build(self):
        import tkinter as tk
        text = _TEXT[self.language]
        self.window.title(text["title"])
        self.window.minsize(560, 560)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        content = tk.Frame(self.window, padx=24, pady=22)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(9, weight=1)
        tk.Label(content, text=text["heading"], font=("TkDefaultFont", 16, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(content, text=text["warning"], fg="#9b1c1c", wraplength=500, justify="left").grid(row=1, column=0, sticky="ew", pady=(4, 18))
        row = 2
        for label, value in ((text["account"], self.preview["account_id"]), (text["to"], ", ".join(self.preview["to"])), (text["subject"], self.preview["subject"])):
            tk.Label(content, text=label, font=("TkDefaultFont", 9, "bold")).grid(row=row, column=0, sticky="w")
            tk.Label(content, text=value, anchor="w", justify="left", wraplength=500, relief="solid", borderwidth=1, padx=8, pady=6).grid(row=row + 1, column=0, sticky="ew", pady=(2, 10))
            row += 2
        tk.Label(content, text=text["body"], font=("TkDefaultFont", 9, "bold")).grid(row=8, column=0, sticky="nw")
        body = tk.Text(content, height=9, wrap="word", padx=8, pady=8)
        body.grid(row=9, column=0, sticky="nsew", pady=(2, 14))
        body.insert("1.0", self.preview["body"])
        body.config(state="disabled")
        self.checked = tk.BooleanVar(value=False)
        tk.Checkbutton(content, text=text["check"], variable=self.checked, command=self._toggle_send).grid(row=10, column=0, sticky="w", pady=(0, 16))
        actions = tk.Frame(content)
        actions.grid(row=11, column=0, sticky="ew")
        actions.columnconfigure(1, weight=1)
        self.cancel_button = tk.Button(actions, text=text["cancel"], command=self._cancel, padx=14, pady=8)
        self.cancel_button.grid(row=0, column=0, sticky="w")
        self.send_button = tk.Button(actions, text=text["send"], command=self._approve, state="disabled", padx=14, pady=8)
        self.send_button.grid(row=0, column=2, sticky="e")
        self.cancel_button.focus_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Escape>", lambda _event: self._cancel())

    def _toggle_send(self):
        self.send_button.config(state="normal" if self.checked.get() else "disabled")

    def _approve(self):
        if self.checked.get():
            self.approved = True
            self.window.destroy()

    def _cancel(self):
        self.approved = False
        self.window.destroy()


def run_send_approval_gui(root: str, account_id: str, draft_id: str, language="es") -> bool:
    """Muestra el borrador validado y retorna la decision local del usuario."""
    import tkinter as tk
    preview = load_send_preview(root, account_id, draft_id)
    window = tk.Tk()
    form = _SendApprovalForm(window, preview, language)
    form.build()
    window.mainloop()
    return form.approved
