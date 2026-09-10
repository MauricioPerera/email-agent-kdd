"""Punto de entrada de modulo: `python -m src.email [args]`.

Delega en cli_main los argumentos de linea de comandos (sin el nombre del
programa) y propaga su codigo de salida.
"""

import sys

from src.email.cli import cli_main

if __name__ == "__main__":
    sys.exit(cli_main(sys.argv[1:]))