"""Tests for src/pipeline.py"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

EXTRACTED = {
    "title": "FISIOLOGÍA CELULAR",
    "microlecciones": [
        {
            "numero": 1,
            "titulo": "Membrana celular",
            "bloques": [
                {
                    "titulo": "Funciones",
                    "nivel": 2,
                    "elementos": [{"type": "paragraph", "segments": [{"type": "text", "text": "La membrana delimita la célula."}]}],
                }
            ],
        }
    ],
}

GENERATED = {
    "title": "FISIOLOGÍA CELULAR",
    "microlecciones": [
        {
            "numero": 1,
            "titulo": "Membrana celular",
            "html": "<section><h2>Funciones</h2><p>La membrana delimita la célula.</p></section>",
            "quiz": {
                "preguntas": [
                    {
                        "nivel_bloom": "recordar",
                        "enunciado": "¿Cuál es la función de la membrana?",
                        "opciones": {"a": "Producir energía", "b": "Delimitar la célula", "c": "Sintetizar proteínas", "d": "Almacenar ADN"},
                        "respuesta_correcta": "b",
                        "explicacion": "La membrana delimita y protege la célula.",
                    }
                ]
            },
        }
    ],
}

UPLOAD_REPORT = {
    "documento_id": "abc-123",
    "microlecciones_subidas": [{"numero": 1, "titulo": "Membrana celular", "staging_id": "xyz-456"}],
}


def _mock_run(tmp_path, skip_upload=False):
    """Call pipeline.run() with all external calls mocked."""
    import sys
    import types
    import src.pipeline as pipeline_mod

    docx = tmp_path / "test.docx"
    docx.write_bytes(b"fake")

    mock_upload = MagicMock(return_value=UPLOAD_REPORT)

    # Inject a fake src.uploader module so the lazy import inside pipeline.run()
    # picks up our mock without needing the real supabase package.
    fake_uploader = types.ModuleType("src.uploader")
    fake_uploader.upload = mock_upload

    with patch.object(pipeline_mod, "extract", return_value=EXTRACTED) as mock_extract, \
         patch.object(pipeline_mod, "generate", return_value=GENERATED) as mock_generate, \
         patch.dict(sys.modules, {"src.uploader": fake_uploader}):

        result = pipeline_mod.run(docx, skip_upload=skip_upload)

    return result, mock_extract, mock_generate, mock_upload


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestRunHappyPath:
    def test_returns_all_keys(self, tmp_path):
        result, *_ = _mock_run(tmp_path)
        assert set(result.keys()) == {"extracted", "generated", "validation_ok", "upload_report"}

    def test_validation_ok_is_true(self, tmp_path):
        result, *_ = _mock_run(tmp_path)
        assert result["validation_ok"] is True

    def test_extracted_in_result(self, tmp_path):
        result, *_ = _mock_run(tmp_path)
        assert result["extracted"]["title"] == "FISIOLOGÍA CELULAR"

    def test_generated_in_result(self, tmp_path):
        result, *_ = _mock_run(tmp_path)
        assert len(result["generated"]["microlecciones"]) == 1

    def test_upload_report_in_result(self, tmp_path):
        result, *_ = _mock_run(tmp_path)
        assert result["upload_report"]["documento_id"] == "abc-123"

    def test_each_stage_called_once(self, tmp_path):
        result, mock_extract, mock_generate, mock_upload = _mock_run(tmp_path)
        mock_extract.assert_called_once()
        mock_generate.assert_called_once()
        mock_upload.assert_called_once()


# ---------------------------------------------------------------------------
# skip_upload flag
# ---------------------------------------------------------------------------

class TestSkipUpload:
    def test_upload_not_called_when_skipped(self, tmp_path):
        _, _, _, mock_upload = _mock_run(tmp_path, skip_upload=True)
        mock_upload.assert_not_called()

    def test_upload_report_is_none_when_skipped(self, tmp_path):
        result, *_ = _mock_run(tmp_path, skip_upload=True)
        assert result["upload_report"] is None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestErrors:
    def test_raises_file_not_found(self, tmp_path):
        import src.pipeline as pipeline_mod
        with pytest.raises(FileNotFoundError):
            pipeline_mod.run(tmp_path / "nonexistent.docx")

    def test_raises_validation_error_on_bad_generated(self, tmp_path):
        import sys, types
        import src.pipeline as pipeline_mod
        from src.validator import ValidationError

        docx = tmp_path / "test.docx"
        docx.write_bytes(b"fake")
        bad_generated = {"title": "", "microlecciones": []}

        fake_uploader = types.ModuleType("src.uploader")
        fake_uploader.upload = MagicMock()

        with patch.object(pipeline_mod, "extract", return_value=EXTRACTED), \
             patch.object(pipeline_mod, "generate", return_value=bad_generated), \
             patch.dict(sys.modules, {"src.uploader": fake_uploader}):
            with pytest.raises(ValidationError):
                pipeline_mod.run(docx)

    def test_upload_not_called_when_validation_fails(self, tmp_path):
        import sys, types
        import src.pipeline as pipeline_mod
        from src.validator import ValidationError

        docx = tmp_path / "test.docx"
        docx.write_bytes(b"fake")

        mock_upload = MagicMock()
        fake_uploader = types.ModuleType("src.uploader")
        fake_uploader.upload = mock_upload

        with patch.object(pipeline_mod, "extract", return_value=EXTRACTED), \
             patch.object(pipeline_mod, "generate", return_value={"title": "", "microlecciones": []}), \
             patch.dict(sys.modules, {"src.uploader": fake_uploader}):
            with pytest.raises(ValidationError):
                pipeline_mod.run(docx)
        mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# Output file saving
# ---------------------------------------------------------------------------

class TestOutputFiles:
    def _run_with_outputs(self, tmp_path, **run_kwargs):
        import sys, types
        import src.pipeline as pipeline_mod
        fake_uploader = types.ModuleType("src.uploader")
        fake_uploader.upload = MagicMock(return_value=UPLOAD_REPORT)
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"fake")
        with patch.object(pipeline_mod, "extract", return_value=EXTRACTED), \
             patch.object(pipeline_mod, "generate", return_value=GENERATED), \
             patch.dict(sys.modules, {"src.uploader": fake_uploader}):
            pipeline_mod.run(docx, **run_kwargs)

    def test_extracted_output_saved(self, tmp_path):
        out = tmp_path / "extracted.json"
        self._run_with_outputs(tmp_path, extracted_output=str(out))
        assert out.exists()
        assert json.loads(out.read_text())["title"] == "FISIOLOGÍA CELULAR"

    def test_generated_output_saved(self, tmp_path):
        out = tmp_path / "generated.json"
        self._run_with_outputs(tmp_path, generated_output=str(out))
        assert out.exists()
        assert len(json.loads(out.read_text())["microlecciones"]) == 1
