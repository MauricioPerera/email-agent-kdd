"""Frontera estructural de proveedor de correo, sin implementacion de red.

``EmailProvider`` es un Protocol (tipado estructural, solo stdlib): define
QUE debe saber hacer un adaptador de proveedor, nunca COMO lo hace. Ningun
metodo conecta, envia, abre credenciales ni escribe disco. Los adaptadores
concretos reciben por ``send_message`` una orden YA confirmada
(``message["confirmed"] is True``); esta interfaz no ofrece ningun camino
para saltarse esa confirmacion.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailProvider(Protocol):
    """Interfaz minima de un proveedor de correo (solo dicts serializables)."""

    def list_messages(self, account: dict, query: str = "") -> list[dict]:
        """Leer mensajes sin conectar: la interpretacion de ``query`` es del
        adaptador concreto (vacio = mensajes recientes). ``account`` es un
        registro serializable a JSON y ``credential_ref`` permanece opaco.
        Devuelve una lista de dicts serializables a JSON."""
        ...

    def send_message(self, account: dict, message: dict) -> dict:
        """Ejecutar una orden YA confirmada: el adaptador concreto recibira
        la decision confirmada (``message["confirmed"] is True``) y debe
        rechazar una orden sin confirmar con ValueError. Esta interfaz no
        valida credenciales ni inicia conexiones. Devuelve un recibo
        serializable a JSON (dict)."""
        ...