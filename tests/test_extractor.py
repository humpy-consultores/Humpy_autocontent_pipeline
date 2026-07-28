"""Tests for src/extractor.py"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(paragraphs: list[tuple[str, str]], img_para_indices: list[int] | None = None):
    """
    Build a mock Document.
    paragraphs: list of (text, style_name)
    img_para_indices: indices of paragraphs that should appear to have inline images
    """
    img_para_indices = set(img_para_indices or [])
    doc = MagicMock()
    paras = []
    for idx, (text, style) in enumerate(paragraphs):
        p = MagicMock()
        p.text = text
        p.style.name = style
        p._p.pPr = None
        # Paragraphs with inline images carry an a:blip tag in their XML
        if idx in img_para_indices:
            p._element.xml = '<a:blip r:embed="rId1"/>'
        else:
            p._element.xml = ""
        paras.append(p)
    doc.paragraphs = paras
    return doc


def _extract_with_mock(paragraphs, img_para_indices=None):
    """Run extract() with a mocked Document and no-op _build_rid_map."""
    from src.extractor import extract
    doc = _make_doc(paragraphs, img_para_indices)
    with patch("src.extractor.Document", return_value=doc), \
         patch("src.extractor._build_rid_map", return_value={}):
        return extract("fake.docx")


# ---------------------------------------------------------------------------
# _parse_inline_tags
# ---------------------------------------------------------------------------

class TestParseInlineTags:
    def test_plain_text(self):
        from src.extractor import _parse_inline_tags
        result = _parse_inline_tags("texto sin etiquetas")
        assert result == [{"type": "text", "text": "texto sin etiquetas"}]

    def test_single_red_tag(self):
        from src.extractor import _parse_inline_tags
        result = _parse_inline_tags("la [ROJO: membrana] es selectiva")
        assert len(result) == 3
        assert result[1] == {"type": "emphasis", "color": "rojo", "text": "membrana"}

    def test_multiple_tags(self):
        from src.extractor import _parse_inline_tags
        result = _parse_inline_tags("[ROJO: A] y [AMARILLO: B]")
        colors = [s["color"] for s in result if s["type"] == "emphasis"]
        assert colors == ["rojo", "amarillo"]

    def test_case_insensitive(self):
        from src.extractor import _parse_inline_tags
        result = _parse_inline_tags("[azul: concepto]")
        assert result[0]["color"] == "azul"


# ---------------------------------------------------------------------------
# extract() — document structure
# ---------------------------------------------------------------------------

class TestExtract:
    def test_title_extracted(self):
        result = _extract_with_mock([
            ("FISIOLOGÍA CELULAR", "Title"),
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
        ])
        assert result["title"] == "FISIOLOGÍA CELULAR"

    def test_microleccion_parsed(self):
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
            ("MICROLECCIÓN 2: Transporte celular", "Heading 1"),
        ])
        assert len(result["microlecciones"]) == 2
        assert result["microlecciones"][0]["numero"] == 1
        assert result["microlecciones"][0]["titulo"] == "Membrana celular"

    def test_bloque_under_microleccion(self):
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
            ("Funciones principales", "Heading 2"),
            ("La membrana protege la célula.", "Normal"),
        ])
        bloques = result["microlecciones"][0]["bloques"]
        assert len(bloques) == 1
        assert bloques[0]["titulo"] == "Funciones principales"
        assert bloques[0]["elementos"][0]["type"] == "paragraph"

    def test_formula_element(self):
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("[FORMULA: GC = Vol × Fr]", "Normal"),
        ])
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "formula"
        assert "GC" in elem["text"]

    def test_img_placeholder_element(self):
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("[IMG: Diagrama de la membrana celular]", "Normal"),
        ])
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "image"
        assert "membrana" in elem["description"]
        assert elem["local_path"] is None

    def test_empty_paragraphs_skipped(self):
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),
            ("Texto real.", "Normal"),
        ])
        elementos = result["microlecciones"][0]["bloques"][0]["elementos"]
        assert len(elementos) == 1
        assert elementos[0]["segments"][0]["text"] == "Texto real."


# ---------------------------------------------------------------------------
# extract() — inline image handling
# ---------------------------------------------------------------------------

class TestInlineImages:
    def test_inline_image_produces_image_element(self):
        """A paragraph with an embedded image yields type=image."""
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),                              # image paragraph (no text)
            ("[IMG: Diagrama de la bicapa]", "Normal"),  # description below
        ], img_para_indices=[2])
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "image"

    def test_inline_image_lookahead_captures_description(self):
        """The [IMG: desc] line immediately after an image becomes its description."""
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),
            ("[IMG: Diagrama de la bicapa lipídica]", "Normal"),
        ], img_para_indices=[2])
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["description"] == "Diagrama de la bicapa lipídica"

    def test_inline_image_description_paragraph_not_duplicated(self):
        """The [IMG: desc] paragraph is consumed by the lookahead, not added as extra element."""
        result = _extract_with_mock([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),
            ("[IMG: Descripción]", "Normal"),
            ("Texto posterior.", "Normal"),
        ], img_para_indices=[2])
        elementos = result["microlecciones"][0]["bloques"][0]["elementos"]
        assert len(elementos) == 2
        assert elementos[0]["type"] == "image"
        assert elementos[1]["type"] == "paragraph"

    def test_inline_image_local_path_from_rid_map(self):
        """When rid_map has the rId, local_path is set on the image element."""
        from src.extractor import extract
        fake_path = Path("/tmp/image1.jpg")

        doc = _make_doc([
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),
        ], img_para_indices=[2])

        with patch("src.extractor.Document", return_value=doc), \
             patch("src.extractor._build_rid_map", return_value={"rId1": fake_path}):
            result = extract("fake.docx")

        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "image"
        assert elem["local_path"] == str(fake_path)
