"""Tests for src/extractor.py"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers to build mock paragraphs
# ---------------------------------------------------------------------------

def _mock_para(text: str, style_name: str, has_image: bool = False):
    para = MagicMock()
    para.text = text
    para.style.name = style_name
    # pPr / numPr — not a list item by default
    para._p.pPr = None
    with patch("src.extractor._has_inline_image", return_value=has_image):
        pass
    para._element.findall = MagicMock(return_value=[MagicMock()] if has_image else [])
    return para


# ---------------------------------------------------------------------------
# Unit tests
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


class TestExtract:
    def _make_doc(self, paragraphs: list[tuple[str, str]]):
        """Build a mock Document with given (text, style) paragraph list."""
        doc = MagicMock()
        paras = []
        for text, style in paragraphs:
            p = MagicMock()
            p.text = text
            p.style.name = style
            p._p.pPr = None
            p._element.xml = ""  # no embedded images
            paras.append(p)
        doc.paragraphs = paras
        return doc

    def test_title_extracted(self):
        from src.extractor import extract
        paragraphs = [
            ("FISIOLOGÍA CELULAR", "Title"),
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        assert result["title"] == "FISIOLOGÍA CELULAR"

    def test_microleccion_parsed(self):
        from src.extractor import extract
        paragraphs = [
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
            ("MICROLECCIÓN 2: Transporte celular", "Heading 1"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        assert len(result["microlecciones"]) == 2
        assert result["microlecciones"][0]["numero"] == 1
        assert result["microlecciones"][0]["titulo"] == "Membrana celular"

    def test_bloque_under_microleccion(self):
        from src.extractor import extract
        paragraphs = [
            ("MICROLECCIÓN 1: Membrana celular", "Heading 1"),
            ("Funciones principales", "Heading 2"),
            ("La membrana protege la célula.", "Normal"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        bloques = result["microlecciones"][0]["bloques"]
        assert len(bloques) == 1
        assert bloques[0]["titulo"] == "Funciones principales"
        assert bloques[0]["elementos"][0]["type"] == "paragraph"

    def test_formula_element(self):
        from src.extractor import extract
        paragraphs = [
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("[FORMULA: GC = Vol × Fr]", "Normal"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "formula"
        assert "GC" in elem["text"]

    def test_img_placeholder_element(self):
        from src.extractor import extract
        paragraphs = [
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("[IMG: Diagrama de la membrana celular]", "Normal"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        elem = result["microlecciones"][0]["bloques"][0]["elementos"][0]
        assert elem["type"] == "image"
        assert "membrana" in elem["description"]

    def test_empty_paragraphs_skipped(self):
        from src.extractor import extract
        paragraphs = [
            ("MICROLECCIÓN 1: Tema", "Heading 1"),
            ("Bloque", "Heading 2"),
            ("", "Normal"),
            ("Texto real.", "Normal"),
        ]
        with patch("src.extractor.Document", return_value=self._make_doc(paragraphs)):
            result = extract("fake.docx")
        elementos = result["microlecciones"][0]["bloques"][0]["elementos"]
        assert len(elementos) == 1
        assert elementos[0]["segments"][0]["text"] == "Texto real."
