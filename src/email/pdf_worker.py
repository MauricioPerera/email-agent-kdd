"""Worker aislado de PDF: stdin bytes -> stdout JSON, sin red ni archivos."""

import json
import sys
from io import BytesIO

if sys.platform == 'linux':
    sys.path.insert(0, '/parser')

from pypdf import PdfReader

MAX_PAGES = 100
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_INPUT_BYTES = 25 * 1024 * 1024


def main():
    content = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    try:
        if len(content) > MAX_INPUT_BYTES:
            raise ValueError("input-limit")
        # Toleramos variaciones menores de xref producidas por clientes de
        # correo; los limites y el manejo fail-closed siguen aplicando.
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted")
        if len(reader.pages) > MAX_PAGES:
            raise ValueError("page-limit")
        chunks = []
        size = 0
        for page in reader.pages:
            chunk = page.extract_text() or ""
            size += len(chunk.encode("utf-8")) + (2 if chunks else 0)
            if size > MAX_OUTPUT_BYTES:
                raise ValueError("output-limit")
            chunks.append(chunk)
        text = "\n\n".join(chunks)
        print(json.dumps({"text": text}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"error": "pdf-rejected"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
