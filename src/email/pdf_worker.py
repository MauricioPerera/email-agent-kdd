"""Worker aislado de PDF: stdin bytes -> stdout JSON, sin red ni archivos."""

import json
import sys
from io import BytesIO

from pypdf import PdfReader

MAX_PAGES = 100
MAX_OUTPUT_BYTES = 4 * 1024 * 1024


def main():
    content = sys.stdin.buffer.read()
    try:
        # Toleramos variaciones menores de xref producidas por clientes de
        # correo; los limites y el manejo fail-closed siguen aplicando.
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted")
        if len(reader.pages) > MAX_PAGES:
            raise ValueError("page-limit")
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise ValueError("output-limit")
        print(json.dumps({"text": text}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"error": "pdf-rejected"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
