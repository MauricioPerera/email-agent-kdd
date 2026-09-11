from pathlib import Path


ROOT = Path(__file__).parents[3]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8").lower()


def test_matrix_names_platforms_and_native_stores():
    text = read("PLATFORM-MATRIX.md")
    for value in ("windows", "macos", "linux", "credential manager", "keychain", "secret service"):
        assert value in text


def test_matrix_is_actionable_and_safe():
    text = read("PLATFORM-MATRIX.md")
    assert "persona no técnica" in text
    assert "setup-gui" in text and "setup ." in text
    assert "no usa archivos de texto" in text
    assert "detenerse" in text
