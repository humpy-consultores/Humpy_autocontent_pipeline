"""
Validator: checks that generator output conforms to the expected schema
before it is handed to the uploader.

Validates:
  - Top-level structure: title, microlecciones list
  - Per microlección: numero, titulo, html, quiz
  - Per quiz: preguntas list with all required fields
  - Bloom levels are from the allowed set
  - opciones contains exactly keys a, b, c, d
  - respuesta_correcta is one of a, b, c, d
  - HTML fragment is non-empty and contains at least one opening tag
"""

import json
import argparse
from pathlib import Path


BLOOM_LEVELS = {"recordar", "comprender", "aplicar", "analizar"}
OPCION_KEYS  = {"a", "b", "c", "d"}


# ---------------------------------------------------------------------------
# Error collection
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s):\n" + "\n".join(f"  - {e}" for e in errors))


# ---------------------------------------------------------------------------
# Field-level checks
# ---------------------------------------------------------------------------

def _check_pregunta(pregunta: dict, prefix: str) -> list[str]:
    errs = []

    for field in ("nivel_bloom", "enunciado", "opciones", "respuesta_correcta", "explicacion"):
        if field not in pregunta:
            errs.append(f"{prefix}: missing field '{field}'")

    nivel = pregunta.get("nivel_bloom", "")
    if nivel and nivel not in BLOOM_LEVELS:
        errs.append(f"{prefix}: invalid nivel_bloom '{nivel}' (expected one of {sorted(BLOOM_LEVELS)})")

    opciones = pregunta.get("opciones")
    if opciones is not None:
        if not isinstance(opciones, dict):
            errs.append(f"{prefix}: 'opciones' must be a dict")
        else:
            missing = OPCION_KEYS - opciones.keys()
            extra   = opciones.keys() - OPCION_KEYS
            if missing:
                errs.append(f"{prefix}: 'opciones' missing keys {sorted(missing)}")
            if extra:
                errs.append(f"{prefix}: 'opciones' has unexpected keys {sorted(extra)}")
            for k, v in opciones.items():
                if not isinstance(v, str) or not v.strip():
                    errs.append(f"{prefix}: opcion '{k}' is empty or not a string")

    rc = pregunta.get("respuesta_correcta", "")
    if rc and rc not in OPCION_KEYS:
        errs.append(f"{prefix}: 'respuesta_correcta' must be one of a/b/c/d, got '{rc}'")

    enunciado = pregunta.get("enunciado", "")
    if isinstance(enunciado, str) and not enunciado.strip():
        errs.append(f"{prefix}: 'enunciado' is empty")

    return errs


def _check_quiz(quiz: dict, prefix: str) -> list[str]:
    errs = []
    if not isinstance(quiz, dict):
        return [f"{prefix}: 'quiz' must be a dict"]

    preguntas = quiz.get("preguntas")
    if preguntas is None:
        return [f"{prefix}: 'quiz' missing 'preguntas' key"]
    if not isinstance(preguntas, list):
        return [f"{prefix}: 'quiz.preguntas' must be a list"]
    if len(preguntas) == 0:
        errs.append(f"{prefix}: 'quiz.preguntas' is empty")

    for idx, p in enumerate(preguntas):
        errs.extend(_check_pregunta(p, f"{prefix} pregunta[{idx}]"))

    return errs


def _check_microleccion(ml: dict, idx: int) -> list[str]:
    errs = []
    prefix = f"microleccion[{idx}]"

    for field in ("numero", "titulo", "html", "quiz"):
        if field not in ml:
            errs.append(f"{prefix}: missing field '{field}'")

    numero = ml.get("numero")
    if numero is not None and not isinstance(numero, int):
        errs.append(f"{prefix}: 'numero' must be an integer")

    titulo = ml.get("titulo", "")
    if isinstance(titulo, str) and not titulo.strip():
        errs.append(f"{prefix}: 'titulo' is empty")

    html = ml.get("html", "")
    if not isinstance(html, str) or not html.strip():
        errs.append(f"{prefix}: 'html' is empty")
    elif "<" not in html:
        errs.append(f"{prefix}: 'html' contains no HTML tags")

    if "quiz" in ml:
        errs.extend(_check_quiz(ml["quiz"], prefix))

    return errs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(generated: dict) -> list[str]:
    """
    Validate generator output dict.

    Returns a list of error strings (empty list means valid).
    Does NOT raise — callers decide whether to treat errors as fatal.
    """
    errs = []

    if not isinstance(generated, dict):
        return ["root: generated output must be a dict"]

    if "title" not in generated:
        errs.append("root: missing 'title' field")
    elif not isinstance(generated["title"], str):
        errs.append("root: 'title' must be a string")

    microlecciones = generated.get("microlecciones")
    if microlecciones is None:
        errs.append("root: missing 'microlecciones' field")
        return errs

    if not isinstance(microlecciones, list):
        errs.append("root: 'microlecciones' must be a list")
        return errs

    if len(microlecciones) == 0:
        errs.append("root: 'microlecciones' is empty")

    for idx, ml in enumerate(microlecciones):
        errs.extend(_check_microleccion(ml, idx))

    return errs


def validate_or_raise(generated: dict) -> None:
    """Validate and raise ValidationError if any errors are found."""
    errs = validate(generated)
    if errs:
        raise ValidationError(errs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate generator JSON output before uploading to Supabase."
    )
    parser.add_argument("--input", required=True, help="Path to generator JSON output")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    errors = validate(data)

    if errors:
        print(f"INVALID — {len(errors)} error(s) found:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    else:
        ml_count = len(data.get("microlecciones", []))
        q_count  = sum(
            len(ml.get("quiz", {}).get("preguntas", []))
            for ml in data.get("microlecciones", [])
        )
        print(f"OK — {ml_count} microlección(es), {q_count} pregunta(s). Ready to upload.")


if __name__ == "__main__":
    main()
