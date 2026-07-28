"""Tests for src/validator.py"""

import pytest
from src.validator import validate, validate_or_raise, ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_pregunta(**overrides):
    p = {
        "nivel_bloom": "recordar",
        "enunciado": "¿Cuál es la función principal de la membrana celular?",
        "opciones": {"a": "Producir energía", "b": "Delimitar la célula", "c": "Sintetizar proteínas", "d": "Almacenar ADN"},
        "respuesta_correcta": "b",
        "explicacion": "La membrana delimita y protege la célula.",
    }
    p.update(overrides)
    return p


def _valid_microleccion(numero=1, **overrides):
    ml = {
        "numero": numero,
        "titulo": "Membrana celular",
        "html": "<section><h2>Membrana</h2><p>Contenido.</p></section>",
        "quiz": {"preguntas": [_valid_pregunta()]},
    }
    ml.update(overrides)
    return ml


def _valid_generated(**overrides):
    g = {
        "title": "FISIOLOGÍA CELULAR",
        "microlecciones": [_valid_microleccion()],
    }
    g.update(overrides)
    return g


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------

class TestTopLevel:
    def test_valid_input_returns_no_errors(self):
        assert validate(_valid_generated()) == []

    def test_non_dict_returns_error(self):
        errs = validate([])
        assert any("must be a dict" in e for e in errs)

    def test_missing_title(self):
        g = _valid_generated()
        del g["title"]
        errs = validate(g)
        assert any("title" in e for e in errs)

    def test_missing_microlecciones(self):
        g = _valid_generated()
        del g["microlecciones"]
        errs = validate(g)
        assert any("microlecciones" in e for e in errs)

    def test_empty_microlecciones_list(self):
        errs = validate(_valid_generated(microlecciones=[]))
        assert any("empty" in e for e in errs)


# ---------------------------------------------------------------------------
# Microlección-level
# ---------------------------------------------------------------------------

class TestMicroleccion:
    def test_missing_numero(self):
        ml = _valid_microleccion()
        del ml["numero"]
        errs = validate(_valid_generated(microlecciones=[ml]))
        assert any("numero" in e for e in errs)

    def test_missing_titulo(self):
        ml = _valid_microleccion()
        del ml["titulo"]
        errs = validate(_valid_generated(microlecciones=[ml]))
        assert any("titulo" in e for e in errs)

    def test_empty_titulo(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(titulo="   ")]))
        assert any("titulo" in e and "empty" in e for e in errs)

    def test_missing_html(self):
        ml = _valid_microleccion()
        del ml["html"]
        errs = validate(_valid_generated(microlecciones=[ml]))
        assert any("html" in e for e in errs)

    def test_empty_html(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(html="")]))
        assert any("html" in e and "empty" in e for e in errs)

    def test_html_without_tags(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(html="solo texto plano")]))
        assert any("html" in e and "tags" in e for e in errs)

    def test_missing_quiz(self):
        ml = _valid_microleccion()
        del ml["quiz"]
        errs = validate(_valid_generated(microlecciones=[ml]))
        assert any("quiz" in e for e in errs)


# ---------------------------------------------------------------------------
# Quiz-level
# ---------------------------------------------------------------------------

class TestQuiz:
    def test_quiz_not_dict(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(quiz=[])]))
        assert any("dict" in e for e in errs)

    def test_missing_preguntas(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(quiz={})]))
        assert any("preguntas" in e for e in errs)

    def test_empty_preguntas(self):
        errs = validate(_valid_generated(microlecciones=[_valid_microleccion(quiz={"preguntas": []})]))
        assert any("empty" in e for e in errs)


# ---------------------------------------------------------------------------
# Pregunta-level
# ---------------------------------------------------------------------------

class TestPregunta:
    def _gen_with_pregunta(self, **overrides):
        return _valid_generated(microlecciones=[
            _valid_microleccion(quiz={"preguntas": [_valid_pregunta(**overrides)]})
        ])

    def test_invalid_bloom_level(self):
        errs = validate(self._gen_with_pregunta(nivel_bloom="inventar"))
        assert any("nivel_bloom" in e for e in errs)

    def test_all_bloom_levels_accepted(self):
        for level in ("recordar", "comprender", "aplicar", "analizar"):
            assert validate(self._gen_with_pregunta(nivel_bloom=level)) == []

    def test_missing_opcion_key(self):
        p = _valid_pregunta()
        del p["opciones"]["d"]
        errs = validate(_valid_generated(microlecciones=[
            _valid_microleccion(quiz={"preguntas": [p]})
        ]))
        assert any("opciones" in e and "missing" in e for e in errs)

    def test_extra_opcion_key(self):
        p = _valid_pregunta()
        p["opciones"]["e"] = "extra"
        errs = validate(_valid_generated(microlecciones=[
            _valid_microleccion(quiz={"preguntas": [p]})
        ]))
        assert any("opciones" in e and "unexpected" in e for e in errs)

    def test_invalid_respuesta_correcta(self):
        errs = validate(self._gen_with_pregunta(respuesta_correcta="e"))
        assert any("respuesta_correcta" in e for e in errs)

    def test_empty_enunciado(self):
        errs = validate(self._gen_with_pregunta(enunciado=""))
        assert any("enunciado" in e for e in errs)

    def test_missing_explicacion(self):
        p = _valid_pregunta()
        del p["explicacion"]
        errs = validate(_valid_generated(microlecciones=[
            _valid_microleccion(quiz={"preguntas": [p]})
        ]))
        assert any("explicacion" in e for e in errs)


# ---------------------------------------------------------------------------
# validate_or_raise
# ---------------------------------------------------------------------------

class TestValidateOrRaise:
    def test_raises_on_invalid(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_or_raise(_valid_generated(microlecciones=[]))
        assert exc_info.value.errors

    def test_no_raise_on_valid(self):
        validate_or_raise(_valid_generated())  # must not raise

    def test_error_message_lists_all_errors(self):
        g = _valid_generated()
        del g["title"]
        g["microlecciones"] = []
        with pytest.raises(ValidationError) as exc_info:
            validate_or_raise(g)
        msg = str(exc_info.value)
        assert "title" in msg
        assert "empty" in msg
