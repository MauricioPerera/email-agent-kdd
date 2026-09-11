"""Contrato congelado para evitar falsos positivos de contacto en el cuerpo."""

from src.email.query import query_email


def test_contact_filter_reads_only_message_headers(tmp_path):
    folder = tmp_path / "store" / "emails"
    folder.mkdir(parents=True)
    (folder / "header.md").write_text(
        "---\nfrom: Ana <ana@example.test>\n---\ntexto", encoding="utf-8"
    )
    (folder / "body.md").write_text(
        "---\nfrom: Bob <bob@example.test>\n---\nana@example.test", encoding="utf-8"
    )
    assert query_email(str(tmp_path), "contact:ana@example.test") == [
        "store/emails/header.md"
    ]


def test_contact_and_delivery_filters_require_address_boundaries(tmp_path):
    folder = tmp_path / "store" / "emails"
    folder.mkdir(parents=True)
    (folder / "longer.md").write_text(
        "---\nfrom: Ana <ana@example.test.invalid>\n"
        "delivered_to: ana@example.test.invalid\n---\ntexto", encoding="utf-8"
    )
    assert query_email(str(tmp_path), "contact:ana@example.test") == []
    assert query_email(str(tmp_path), "para:ana@example.test") == []
