"""
Extractor: reads a standardized .docx and returns a structured list of microlecciones.

Expected Word structure:
  - Title style      → document title
  - Heading 1        → MICROLECCIÓN N: <title>  (page break before each)
  - Heading 2        → block/section name
  - Heading 3        → sub-block name (optional)
  - Normal           → body text, [IMG: desc], [FORMULA: ...], [ROJO:], [AMARILLO:], [AZUL:]
  - List Bullet/Number → list items
"""

import re
import argparse
import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn  # used to resolve a:blip namespace at import time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MICROLECCION_RE = re.compile(
    r"MICROLECCIÓN\s+(\d+)\s*:\s*(.+)", re.IGNORECASE
)
IMG_RE = re.compile(r"\[IMG:\s*(.+?)\]", re.IGNORECASE)
FORMULA_RE = re.compile(r"\[FORMULA:\s*(.+?)\]", re.IGNORECASE)
COLOR_TAG_RE = re.compile(
    r"\[(ROJO|AMARILLO|AZUL):\s*(.+?)\]", re.IGNORECASE
)


def _para_style(para) -> str:
    """Normalize paragraph style name to lowercase, e.g. 'heading 1'."""
    return para.style.name.lower().strip()


_BLIP_TAG = qn("a:blip")


def _has_inline_image(para) -> bool:
    xml = para._element.xml if hasattr(para._element, "xml") else ""
    return _BLIP_TAG in xml or "v:imagedata" in xml


def _clean_text(text: str) -> str:
    return text.strip()


def _parse_inline_tags(text: str) -> list[dict]:
    """
    Split a paragraph text into segments, separating plain text from
    [ROJO:], [AMARILLO:], [AZUL:] tags.
    Returns list of {"type": "text"|"emphasis", "color": ..., "text": ...}
    """
    segments = []
    last = 0
    for m in COLOR_TAG_RE.finditer(text):
        if m.start() > last:
            plain = text[last:m.start()].strip()
            if plain:
                segments.append({"type": "text", "text": plain})
        segments.append({
            "type": "emphasis",
            "color": m.group(1).lower(),
            "text": m.group(2).strip(),
        })
        last = m.end()
    if last < len(text):
        plain = text[last:].strip()
        if plain:
            segments.append({"type": "text", "text": plain})
    return segments or [{"type": "text", "text": text}]


def _para_to_element(para) -> dict | None:
    """Convert a paragraph to a pipeline element dict, or None if empty."""
    style = _para_style(para)
    text = _clean_text(para.text)

    # Inline image — body paragraph with an embedded image
    if _has_inline_image(para):
        img_match = IMG_RE.search(text)
        return {
            "type": "image",
            "description": img_match.group(1).strip() if img_match else text or "",
        }

    # Explicit [IMG:] line without actual embedded image (placeholder)
    img_match = IMG_RE.fullmatch(text) if text else None
    if img_match:
        return {"type": "image", "description": img_match.group(1).strip()}

    # Formula
    formula_match = FORMULA_RE.fullmatch(text) if text else None
    if formula_match:
        return {"type": "formula", "text": formula_match.group(1).strip()}

    # List items
    if "list" in style or para.style.name.startswith("List"):
        if not text:
            return None
        pPr = para._p.pPr
        level = pPr.numPr.ilvl.val if (pPr is not None and pPr.numPr is not None) else 0
        return {"type": "list_item", "text": text, "level": level}

    # Normal body text
    if style == "normal" and text:
        return {"type": "paragraph", "segments": _parse_inline_tags(text)}

    return None


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract(docx_path: str | Path) -> dict:
    """
    Parse a standardized .docx file and return structured data.

    Returns:
    {
      "title": "FISIOLOGÍA CELULAR",
      "microlecciones": [
        {
          "numero": 1,
          "titulo": "Membrana celular",
          "bloques": [
            {
              "titulo": "MEMBRANA CELULAR",
              "nivel": 2,
              "elementos": [
                {"type": "paragraph", "segments": [{"type": "text", "text": "..."}]},
                {"type": "list_item", "text": "...", "level": 0},
                {"type": "image", "description": "..."},
                {"type": "formula", "text": "..."},
              ]
            }
          ]
        }
      ]
    }
    """
    doc = Document(docx_path)
    result = {"title": "", "microlecciones": []}

    current_microleccion: dict | None = None
    current_bloque: dict | None = None

    for para in doc.paragraphs:
        style = _para_style(para)
        text = _clean_text(para.text)

        # ---- Document title ------------------------------------------------
        if style == "title":
            if text:
                result["title"] = text
            continue

        # ---- Microlección (Heading 1) --------------------------------------
        if style == "heading 1":
            match = MICROLECCION_RE.match(text)
            if match:
                numero = int(match.group(1))
                titulo = match.group(2).strip()
            else:
                # Heading 1 that doesn't match pattern — treat as microlección anyway
                numero = len(result["microlecciones"]) + 1
                titulo = text

            current_bloque = None
            current_microleccion = {
                "numero": numero,
                "titulo": titulo,
                "bloques": [],
            }
            result["microlecciones"].append(current_microleccion)
            continue

        # ---- Block (Heading 2) ---------------------------------------------
        if style == "heading 2":
            if current_microleccion is None:
                # Content before any Heading 1 — create implicit microlección
                current_microleccion = {"numero": 0, "titulo": "", "bloques": []}
                result["microlecciones"].append(current_microleccion)

            current_bloque = {"titulo": text, "nivel": 2, "elementos": []}
            current_microleccion["bloques"].append(current_bloque)
            continue

        # ---- Sub-block (Heading 3) -----------------------------------------
        if style == "heading 3":
            if current_microleccion is None:
                continue
            current_bloque = {"titulo": text, "nivel": 3, "elementos": []}
            current_microleccion["bloques"].append(current_bloque)
            continue

        # ---- Body content --------------------------------------------------
        element = _para_to_element(para)
        if element is None:
            continue

        if current_microleccion is None:
            continue  # skip content before any heading

        if current_bloque is None:
            # Body content before the first Heading 2 — implicit block
            current_bloque = {"titulo": "", "nivel": 2, "elementos": []}
            current_microleccion["bloques"].append(current_bloque)

        current_bloque["elementos"].append(element)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract structured content from a standardized .docx file."
    )
    parser.add_argument("--input", required=True, help="Path to the .docx file")
    parser.add_argument("--output", help="Path to write JSON output (default: stdout)")
    args = parser.parse_args()

    data = extract(args.input)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
