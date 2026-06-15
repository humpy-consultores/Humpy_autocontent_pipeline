"""Tests for src/generator.py"""

import json
import pytest
from unittest.mock import MagicMock, patch


SAMPLE_EXTRACTED = {
    "title": "FISIOLOGÍA CELULAR",
    "microlecciones": [
        {
            "numero": 1,
            "titulo": "Membrana celular",
            "bloques": [
                {
                    "titulo": "Funciones",
                    "nivel": 2,
                    "elementos": [
                        {
                            "type": "paragraph",
                            "segments": [
                                {"type": "text", "text": "La membrana protege la célula."}
                            ],
                        },
                        {"type": "list_item", "text": "Permeabilidad selectiva", "level": 0},
                        {"type": "formula", "text": "GC = Vol × Fr"},
                        {"type": "image", "description": "Diagrama bicapa lipídica"},
                    ],
                }
            ],
        }
    ],
}

SAMPLE_QUIZ = {
    "preguntas": [
        {
            "nivel_bloom": "recordar",
            "enunciado": "¿Cuál es la función principal de la membrana celular?",
            "opciones": {
                "a": "Producir energía",
                "b": "Delimitar y proteger la célula",
                "c": "Sintetizar proteínas",
                "d": "Almacenar ADN",
            },
            "respuesta_correcta": "b",
            "explicacion": "La membrana delimita y protege la célula.",
        }
    ]
}


def _make_client(html_response: str, quiz_response: str):
    client = MagicMock()

    html_msg = MagicMock()
    html_msg.content = [MagicMock(text=html_response)]

    quiz_msg = MagicMock()
    quiz_msg.content = [MagicMock(text=json.dumps(quiz_response))]

    client.messages.create.side_effect = [html_msg, quiz_msg]
    return client


class TestElementsToText:
    def test_paragraph_segments(self):
        from src.generator import _elements_to_text
        elementos = [{"type": "paragraph", "segments": [{"text": "Hola"}, {"text": "mundo"}]}]
        assert "Hola mundo" in _elements_to_text(elementos)

    def test_list_item(self):
        from src.generator import _elements_to_text
        elementos = [{"type": "list_item", "text": "Item A", "level": 0}]
        assert "Item A" in _elements_to_text(elementos)

    def test_formula(self):
        from src.generator import _elements_to_text
        elementos = [{"type": "formula", "text": "GC = Vol × Fr"}]
        assert "GC" in _elements_to_text(elementos)

    def test_image(self):
        from src.generator import _elements_to_text
        elementos = [{"type": "image", "description": "Diagrama celular"}]
        assert "Diagrama celular" in _elements_to_text(elementos)


class TestMicroleccionToPrompt:
    def test_includes_titulo(self):
        from src.generator import _microleccion_to_prompt
        ml = SAMPLE_EXTRACTED["microlecciones"][0]
        prompt = _microleccion_to_prompt(ml)
        assert "Membrana celular" in prompt
        assert "Funciones" in prompt


class TestGenerateMicroleccionHtml:
    def test_returns_html_string(self):
        from src.generator import generate_microleccion_html
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="<section>Contenido</section>")]
        )
        ml = SAMPLE_EXTRACTED["microlecciones"][0]
        result = generate_microleccion_html(client, ml)
        assert result == "<section>Contenido</section>"

    def test_calls_correct_model(self):
        from src.generator import generate_microleccion_html, MODEL
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="<p>ok</p>")]
        )
        generate_microleccion_html(client, SAMPLE_EXTRACTED["microlecciones"][0])
        call_kwargs = client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == MODEL


class TestGenerateQuiz:
    def test_returns_parsed_dict(self):
        from src.generator import generate_quiz
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(SAMPLE_QUIZ))]
        )
        result = generate_quiz(client, SAMPLE_EXTRACTED["microlecciones"][0], "<p>html</p>")
        assert "preguntas" in result
        assert len(result["preguntas"]) == 1

    def test_strips_markdown_fences(self):
        from src.generator import generate_quiz
        client = MagicMock()
        fenced = f"```json\n{json.dumps(SAMPLE_QUIZ)}\n```"
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=fenced)]
        )
        result = generate_quiz(client, SAMPLE_EXTRACTED["microlecciones"][0], "<p>html</p>")
        assert "preguntas" in result


class TestGenerate:
    def test_full_pipeline_output_structure(self):
        from src.generator import generate
        with patch("src.generator.anthropic.Anthropic") as MockAnthropic:
            client = _make_client("<section>HTML</section>", SAMPLE_QUIZ)
            MockAnthropic.return_value = client
            result = generate(SAMPLE_EXTRACTED, n_questions=1)

        assert result["title"] == "FISIOLOGÍA CELULAR"
        assert len(result["microlecciones"]) == 1
        ml = result["microlecciones"][0]
        assert ml["numero"] == 1
        assert ml["titulo"] == "Membrana celular"
        assert "<section>" in ml["html"]
        assert "preguntas" in ml["quiz"]

    def test_two_api_calls_per_microleccion(self):
        from src.generator import generate
        with patch("src.generator.anthropic.Anthropic") as MockAnthropic:
            client = _make_client("<p>HTML</p>", SAMPLE_QUIZ)
            MockAnthropic.return_value = client
            generate(SAMPLE_EXTRACTED, n_questions=1)

        assert client.messages.create.call_count == 2
