"""Formulario tkinter local para el alta segura de cuentas, no tecnico.

UNA ventana estandar local (sin navegador, sin servidor HTTP, sin
procesos externos) con solo `email` y `password` (`show="*"`): el
usuario jamas introduce `account_id` ni elige proveedor. El
`account_id` se DERIVA de forma determinista y segura desde el correo
(etiqueta `custom` documentada). Al pulsar Guardar se llama UNA vez
`discover_mail_servers(email)` SIN contrasena: si confirma ambos
servidores se muestra una confirmacion publica y se continua; si no,
la MISMA ventana revela una seccion avanzada amigable (servidor de
entrada/salida y puerto) validada con las reglas del almacen. Con los
servidores resueltos se llama `provision_windows_email_account` (el
secreto viaja DIRECTAMENTE en memoria desde el widget; jamas se
imprime, registra, escribe, retorna ni envia) y despues
`store_mail_server_config`: la referencia `wincred://` va solo a
`accounts.json` y los hosts solo a `.email-agent/mail-servers.json`.
Cancelar no escribe nada; todo fallo limpia el password y muestra un
mensaje generico; si Credential Manager no esta disponible PARAR claro
sin ofrecer fallback inseguro.
"""

import re

from src.email.discover_mail_servers import discover_mail_servers
from src.email.mail_server_store import store_mail_server_config
from src.email.provision_account import provision_windows_email_account

_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HOST_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$")
_UNSAFE_CHARS = re.compile(r"[^a-z0-9._-]+")
_DASH_RUNS = re.compile(r"-{2,}")
# "email-" + account_id <= 64 (limite de la etiqueta wincred).
_ACCOUNT_ID_MAX = 57
_PROVIDER = "custom"
_STOP_MESSAGE = (
    "PARAR: el almacenamiento seguro de Windows no esta disponible en "
    "este sistema; no existe alternativa segura"
)
_GENERIC_ERROR = "error generico: no se pudo guardar la cuenta"
_EMPTY_FIELDS = "error generico: escriba su correo y su contrasena"
_ADVANCED_TITLE = "Configuracion avanzada del servidor de correo"
_DISCOVERY_GUIDE = (
    "No pudimos detectar los servidores de tu correo automaticamente; "
    "completa la seccion avanzada y vuelve a pulsar Guardar."
)
_DISCOVERY_CONFIRMED = (
    "Detectamos los servidores de tu correo; guardando la cuenta..."
)
_INCOMPLETE = "error generico: faltan datos del servidor de correo"


def _derive_account_id(email: str) -> str:
    """Derivar un account_id determinista y seguro desde el correo."""
    local, _, domain = email.partition("@")
    safe = _UNSAFE_CHARS.sub("-", (local + "-" + domain).lower())
    safe = _DASH_RUNS.sub("-", safe).strip("-._")[:_ACCOUNT_ID_MAX]
    return safe.strip("-._") or "cuenta"


def _parse_port(text: str):
    """Puerto int entre 1 y 65535, o None si el texto no es valido."""
    try:
        port = int(text.strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


def _valid_host(host: str) -> bool:
    """Mismas reglas de host del almacen de servidores (mail-servers.json)."""
    return (
        host != ""
        and len(host) <= 253
        and ".." not in host
        and _HOST_PATTERN.match(host) is not None
    )


class _SetupForm:
    """Ventana de alta segura; el secreto vive solo en el widget password."""

    def __init__(self, master, root: str):
        self.window = master
        self.root = root
        self.code = 1
        self.servers = None
        self.discovery_done = False

    def build(self):
        """Construir los campos publicos, el estado y la seccion avanzada."""
        import tkinter as tk
        window = self.window
        window.title("Configuracion segura de cuenta")
        tk.Label(window, text="Correo electronico").grid(
            row=0, column=0, sticky="w"
        )
        self.email = tk.Entry(window, width=32)
        self.email.grid(row=0, column=1, sticky="w")
        tk.Label(window, text="Contrasena").grid(row=1, column=0, sticky="w")
        self.password = tk.Entry(window, show="*", width=32)
        self.password.grid(row=1, column=1, sticky="w")
        self.status = tk.Label(window, text="", wraplength=360, justify="left")
        self.status.grid(row=2, column=0, columnspan=2, sticky="w")
        tk.Button(window, text="Guardar", command=self._on_save).grid(
            row=3, column=0, sticky="w"
        )
        tk.Button(window, text="Cancelar", command=self._on_cancel).grid(
            row=3, column=1, sticky="w"
        )
        self._build_advanced(window)
        window.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_advanced(self, window):
        """Seccion avanzada oculta: solo hosts y puertos, sin mas terminos."""
        import tkinter as tk
        frame = tk.LabelFrame(window, text=_ADVANCED_TITLE)
        fields = (
            ("Servidor de entrada (IMAP)", "imap_host"),
            ("Puerto de entrada", "imap_port"),
            ("Servidor de salida (SMTP)", "smtp_host"),
            ("Puerto de salida", "smtp_port"),
        )
        for row, (text, attr) in enumerate(fields):
            tk.Label(frame, text=text).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(frame)
            entry.grid(row=row, column=1)
            setattr(self, attr, entry)
        frame.grid(row=4, column=0, columnspan=2, sticky="w")
        frame.grid_remove()
        self.advanced = frame

    def _note(self, message: str):
        """Mensaje generico no terminal: la sesion continua en la ventana."""
        self.status.config(text=message)

    def _clear_password(self):
        self.password.delete(0, "end")

    def _show(self, message: str, kind: str):
        """Limpiar el password y mostrar UN mensaje generico terminal."""
        self._clear_password()
        import tkinter.messagebox
        dialogs = {
            "info": tkinter.messagebox.showinfo,
            "error": tkinter.messagebox.showerror,
            "warning": tkinter.messagebox.showwarning,
        }
        dialogs[kind](
            "configuracion de cuenta", message, parent=self.window
        )

    def _finish(self, code: int):
        """Cerrar la ventana fijando el codigo de salida; limpia el password."""
        self._clear_password()
        self.code = code
        self.window.destroy()

    def _on_cancel(self):
        """Cancelar o cerrar la ventana: cero provision y cero escrituras."""
        self._finish(1)

    def _read_advanced(self):
        """Leer y validar la seccion avanzada; None si incompleta o invalida."""
        imap_host = self.imap_host.get().strip().lower()
        smtp_host = self.smtp_host.get().strip().lower()
        imap_port = _parse_port(self.imap_port.get())
        smtp_port = _parse_port(self.smtp_port.get())
        if (
            imap_host == ""
            or smtp_host == ""
            or imap_port is None
            or smtp_port is None
            or not _valid_host(imap_host)
            or not _valid_host(smtp_host)
        ):
            return None
        return {
            "imap_host": imap_host,
            "imap_port": imap_port,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
        }

    def _discover(self, email: str) -> bool:
        """Descubrir con el email solamente; jamas lee el password."""
        try:
            self.servers = discover_mail_servers(email)
        except ValueError:
            self.advanced.grid()
            self._note(_DISCOVERY_GUIDE)
            return False
        except Exception:
            self._show(_GENERIC_ERROR, "error")
            self._finish(1)
            return False
        return True

    def _on_save(self):
        """Pipeline de Guardar: descubrir, derivar, provisionar y guardar."""
        email = self.email.get().strip()
        if email == "" or self.password.get() == "":
            self._note(_EMPTY_FIELDS)
            return
        if self.servers is None:
            if not self.discovery_done:
                self.discovery_done = True
                if not self._discover(email):
                    return
                self._note(_DISCOVERY_CONFIRMED)
            else:
                self.servers = self._read_advanced()
                if self.servers is None:
                    self._note(_INCOMPLETE)
                    return
        self._provision(email)

    def _provision(self, email: str):
        """Derivar el id, provisionar UNA vez y persistir los servidores."""
        account_id = _derive_account_id(email)
        label = "email-" + account_id
        if _LABEL_PATTERN.match(label) is None:
            self._show(_GENERIC_ERROR, "error")
            self._finish(1)
            return
        try:
            record = provision_windows_email_account(
                self.root,
                account_id,
                _PROVIDER,
                email,
                label,
                self.password.get(),
            )
        except RuntimeError:
            self._show(_STOP_MESSAGE, "warning")
        except Exception:
            self._show(_GENERIC_ERROR, "error")
        else:
            if self._store_servers(account_id):
                self._show("cuenta guardada: " + record["account_id"], "info")
                self._finish(0)
                return
            self._show(_GENERIC_ERROR, "error")
        self._finish(1)

    def _store_servers(self, account_id: str) -> bool:
        """Persistir SOLO los hosts/puertos resueltos; jamas secretos."""
        try:
            store_mail_server_config(self.root, account_id, self.servers)
        except Exception:
            return False
        return True


def run_account_setup_gui(root: str) -> int:
    """Abrir el formulario de alta segura y retornar el codigo de salida.

    Tkinter se importa SOLO aqui: importar este modulo jamas crea
    ventanas ni toca el toolkit. Codigo `0` tras guardar; `1` para
    cancelacion o fallo terminal de provision.
    """
    import tkinter as tk
    window = tk.Tk()
    form = _SetupForm(window, root)
    form.build()
    window.mainloop()
    return form.code