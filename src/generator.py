"""
Generator: calls Claude API to produce microlección HTML and quiz questions
from the structured JSON output of extractor.py.

Chained prompt strategy:
  Step 1 — Generate HTML content for a microlección.
  Step 2 — Generate quiz questions using that HTML as context.
"""

import json
import argparse
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-8"

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_MICROLECCION = """\
Eres un experto en diseño instruccional para ciencias de la salud. Tu tarea es convertir \
contenido académico estructurado en una microlección clara, concisa y visualmente organizada \
en HTML semántico.

Reglas:
- Usa etiquetas HTML semánticas: <section>, <h2>, <h3>, <p>, <ul>, <ol>, <li>.
- Resalta conceptos críticos con clases CSS:
    <span class="red">texto</span>        — concepto de alta importancia
    <span class="highlight-yellow">texto</span> — concepto para memorizar
    <span style="color:#1976d2;font-weight:bold">texto</span> — concepto clave adicional
- Para fórmulas, usa <code class="formula">...</code>.
- Para imágenes usa <figure><img src="PLACEHOLDER" alt="descripción"><figcaption>descripción</figcaption></figure>.
- No incluyas <!DOCTYPE>, <html>, <head> ni <body> — solo el fragmento interno.
- El texto debe estar en español, ser directo y adecuado para estudiantes universitarios.
- No agregues información que no esté en el contenido provisto.
"""

_SYSTEM_QUIZ = """\
Eres un experto en evaluación educativa para ciencias de la salud. Tu tarea es generar \
preguntas de opción múltiple de alta calidad basadas en una microlección dada.

Reglas de las preguntas:
- Genera exactamente {n_questions} preguntas.
- Cada pregunta debe tener exactamente 4 opciones (a, b, c, d).
- Solo una opción es correcta.
- Los distractores deben ser plausibles pero claramente incorrectos para quien estudió.
- Varía los niveles cognitivos de Bloom: recordar, comprender, aplicar, analizar.
- No uses preguntas de "¿cuál NO es...?" ni dobles negaciones.
- El texto debe estar en español.

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta, sin explicaciones adicionales:
{{
  "preguntas": [
    {{
      "nivel_bloom": "recordar|comprender|aplicar|analizar",
      "enunciado": "...",
      "opciones": {{"a": "...", "b": "...", "c": "...", "d": "..."}},
      "respuesta_correcta": "a|b|c|d",
      "explicacion": "Breve justificación de por qué es correcta."
    }}
  ]
}}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _elements_to_text(elementos: list[dict]) -> str:
    """Flatten element list to plain text for the prompt."""
    lines = []
    for el in elementos:
        t = el.get("type")
        if t == "paragraph":
            parts = [s.get("text", "") for s in el.get("segments", [])]
            lines.append(" ".join(parts))
        elif t == "list_item":
            lines.append(f"  • {el.get('text', '')}")
        elif t == "formula":
            lines.append(f"[FÓRMULA: {el.get('text', '')}]")
        elif t == "image":
            lines.append(f"[IMAGEN: {el.get('description', '')}]")
    return "\n".join(lines)


def _microleccion_to_prompt(microleccion: dict) -> str:
    """Serialize one microlección dict to a structured plain-text prompt."""
    lines = [f"# MICROLECCIÓN {microleccion['numero']}: {microleccion['titulo']}\n"]
    for bloque in microleccion.get("bloques", []):
        level = "#" * bloque.get("nivel", 2)
        lines.append(f"{level} {bloque['titulo']}\n")
        lines.append(_elements_to_text(bloque.get("elementos", [])))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

def generate_microleccion_html(client: anthropic.Anthropic, microleccion: dict) -> str:
    """Step 1: generate HTML for a single microlección."""
    user_content = (
        "Convierte la siguiente microlección en HTML semántico siguiendo las reglas del sistema:\n\n"
        + _microleccion_to_prompt(microleccion)
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_SYSTEM_MICROLECCION,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text.strip()


def generate_quiz(
    client: anthropic.Anthropic,
    microleccion: dict,
    html_content: str,
    n_questions: int = 5,
) -> dict:
    """Step 2: generate quiz questions using the microlección HTML as context."""
    system = _SYSTEM_QUIZ.format(n_questions=n_questions)
    user_content = (
        f"Genera {n_questions} preguntas de opción múltiple para la siguiente microlección.\n\n"
        f"### Microlección: {microleccion['titulo']}\n\n"
        f"Contenido HTML generado:\n{html_content}\n\n"
        "Devuelve únicamente el JSON solicitado."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(extracted: dict, n_questions: int = 5, api_key: str | None = None) -> dict:
    """
    Generate microlección HTML and quiz questions from extractor output.

    Args:
        extracted:    dict returned by extractor.extract()
        n_questions:  number of quiz questions per microlección
        api_key:      Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        {
          "title": "...",
          "microlecciones": [
            {
              "numero": 1,
              "titulo": "...",
              "html": "<section>...</section>",
              "quiz": {
                "preguntas": [
                  {
                    "nivel_bloom": "...",
                    "enunciado": "...",
                    "opciones": {"a": "...", "b": "...", "c": "...", "d": "..."},
                    "respuesta_correcta": "a",
                    "explicacion": "..."
                  }
                ]
              }
            }
          ]
        }
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    result = {"title": extracted.get("title", ""), "microlecciones": []}

    for ml in extracted.get("microlecciones", []):
        html = generate_microleccion_html(client, ml)
        quiz = generate_quiz(client, ml, html, n_questions=n_questions)
        result["microlecciones"].append(
            {
                "numero": ml["numero"],
                "titulo": ml["titulo"],
                "html": html,
                "quiz": quiz,
            }
        )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate microlección HTML and quiz from extractor JSON."
    )
    parser.add_argument("--input", required=True, help="Path to extractor JSON output")
    parser.add_argument("--output", help="Path to write generator JSON (default: stdout)")
    parser.add_argument("--questions", type=int, default=5, help="Quiz questions per microlección")
    args = parser.parse_args()

    extracted = json.loads(Path(args.input).read_text(encoding="utf-8"))
    data = generate(extracted, n_questions=args.questions)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
