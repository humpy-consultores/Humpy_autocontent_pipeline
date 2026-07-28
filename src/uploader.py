"""
Uploader: inserts validated generator output into Supabase staging tables.

Flow per microlección:
  1. Upload each image (local_path) to Supabase Storage → get public URL
  2. Replace PLACEHOLDER in HTML with real image URLs
  3. Insert record into staging_microlecciones
  4. Insert each quiz question into staging_preguntas

Human reviewers then approve/reject from the staging tables before
content goes live.
"""

import json
import os
import re
import uuid
from pathlib import Path

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

STORAGE_BUCKET = "microleccion-images"


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------

def upload_image(client: Client, local_path: str, doc_title: str) -> str:
    """
    Upload a local image file to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    path = Path(local_path)
    suffix = path.suffix.lower()
    content_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    storage_key = f"{doc_title}/{uuid.uuid4().hex}{suffix}"
    data = path.read_bytes()

    client.storage.from_(STORAGE_BUCKET).upload(
        storage_key,
        data,
        file_options={"content-type": content_type},
    )

    public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(storage_key)
    return public_url


def _replace_image_placeholders(html: str, url_map: dict[str, str]) -> str:
    """Replace PLACEHOLDER src attributes with real URLs from url_map."""
    for placeholder, url in url_map.items():
        html = html.replace(placeholder, url)
    return html


# ---------------------------------------------------------------------------
# Staging inserts
# ---------------------------------------------------------------------------

def upload_microleccion(
    client: Client,
    documento_id: str,
    microleccion: dict,
    generated_html: str,
    quiz: dict,
) -> str:
    """
    Insert one microlección and its quiz questions into staging tables.
    Returns the staging_microleccion id.
    """
    ml_id = str(uuid.uuid4())

    client.table("staging_microlecciones").insert({
        "id": ml_id,
        "documento_id": documento_id,
        "numero": microleccion["numero"],
        "titulo": microleccion["titulo"],
        "html": generated_html,
        "estado": "pendiente",
    }).execute()

    for pregunta in quiz.get("preguntas", []):
        client.table("staging_preguntas").insert({
            "id": str(uuid.uuid4()),
            "microleccion_id": ml_id,
            "nivel_bloom": pregunta["nivel_bloom"],
            "enunciado": pregunta["enunciado"],
            "opciones": pregunta["opciones"],
            "respuesta_correcta": pregunta["respuesta_correcta"],
            "explicacion": pregunta["explicacion"],
            "estado": "pendiente",
        }).execute()

    return ml_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload(generated: dict, extracted: dict, supabase_url: str | None = None,
           supabase_key: str | None = None) -> dict:
    """
    Upload all content from generator output to Supabase staging tables.

    Args:
        generated:     dict returned by generator.generate()
        extracted:     dict returned by extractor.extract() — used to read local_path
        supabase_url:  override SUPABASE_URL env var
        supabase_key:  override SUPABASE_KEY env var

    Returns:
        {
          "documento_id": "...",
          "microlecciones_subidas": [
            {"numero": 1, "titulo": "...", "staging_id": "..."}
          ]
        }
    """
    if supabase_url:
        os.environ["SUPABASE_URL"] = supabase_url
    if supabase_key:
        os.environ["SUPABASE_KEY"] = supabase_key

    client = _get_client()
    doc_title = generated.get("title", "sin-titulo")

    # Register the document
    documento_id = str(uuid.uuid4())
    client.table("documentos").insert({
        "id": documento_id,
        "titulo_curso": doc_title,
        "estado": "completado",
    }).execute()

    # Build a fast-lookup map: (numero) → bloques with images
    extracted_ml_map = {ml["numero"]: ml for ml in extracted.get("microlecciones", [])}

    result = {"documento_id": documento_id, "microlecciones_subidas": []}

    for gen_ml in generated.get("microlecciones", []):
        numero = gen_ml["numero"]
        html   = gen_ml["html"]
        quiz   = gen_ml["quiz"]

        # Upload images and build placeholder→url map
        url_map: dict[str, str] = {}
        ext_ml = extracted_ml_map.get(numero, {})

        for bloque in ext_ml.get("bloques", []):
            for elem in bloque.get("elementos", []):
                if elem.get("type") == "image" and elem.get("local_path"):
                    local_path = elem["local_path"]
                    if Path(local_path).exists():
                        public_url = upload_image(client, local_path, doc_title)
                        # The generator uses "PLACEHOLDER" as src; replace all occurrences
                        # by matching the alt text to narrow down which placeholder to swap.
                        desc = elem.get("description", "")
                        pattern = f'src="PLACEHOLDER" alt="{desc}"'
                        replacement = f'src="{public_url}" alt="{desc}"'
                        html = html.replace(pattern, replacement)

        # Fallback: replace any remaining bare PLACEHOLDERs
        html = html.replace('src="PLACEHOLDER"', 'src=""')

        staging_id = upload_microleccion(
            client, documento_id, gen_ml, html, quiz
        )
        result["microlecciones_subidas"].append({
            "numero": numero,
            "titulo": gen_ml["titulo"],
            "staging_id": staging_id,
        })

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Upload generator output to Supabase staging tables."
    )
    parser.add_argument("--generated", required=True, help="Path to generator JSON output")
    parser.add_argument("--extracted", required=True, help="Path to extractor JSON output")
    parser.add_argument("--output", help="Path to write upload report JSON (default: stdout)")
    args = parser.parse_args()

    generated = json.loads(Path(args.generated).read_text(encoding="utf-8"))
    extracted = json.loads(Path(args.extracted).read_text(encoding="utf-8"))

    report = upload(generated, extracted)
    output = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
