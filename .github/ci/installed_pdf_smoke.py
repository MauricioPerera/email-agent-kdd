"""Exercise the installed PDF worker, outside the checkout and import path."""
import json
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from src.email import pdf_sandbox

checkout = Path(sys.argv[1]).resolve()
assert checkout not in Path(pdf_sandbox.__file__).resolve().parents
writer = PdfWriter()
page = writer.add_blank_page(width=612, height=792)
font = DictionaryObject({
    NameObject('/Type'): NameObject('/Font'),
    NameObject('/Subtype'): NameObject('/Type1'),
    NameObject('/BaseFont'): NameObject('/Helvetica'),
})
page[NameObject('/Resources')] = DictionaryObject({
    NameObject('/Font'): DictionaryObject({NameObject('/F1'): font}),
})
stream = DecodedStreamObject()
stream.set_data(b'BT /F1 12 Tf 72 720 Td (installed sandbox evidence) Tj ET')
page[NameObject('/Contents')] = stream
data = BytesIO()
writer.write(data)
with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    try:
        assert checkout not in Path.cwd().parents
        if sys.platform == 'linux':
            result = pdf_sandbox.run_pdf(data.getvalue())
            assert result.returncode == 0
            assert json.loads(result.stdout)['text'].strip() == 'installed sandbox evidence'
        else:
            try:
                pdf_sandbox.run_pdf(data.getvalue())
            except pdf_sandbox.SandboxUnavailable:
                pass
            else:
                raise AssertionError('unsupported platform did not fail closed')
    finally:
        # Windows cannot remove a directory while it is the process cwd.
        os.chdir(checkout)
print('Installed PDF sandbox smoke passed')
