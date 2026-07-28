"""
Extractor: reads a standardized .docx and returns structured microlecciones.

Expected Word structure:
  - Title style        → document title
  - Heading 1          → MICROLECCIÓN N: <title>
  - Heading 2          → block/section name
  - Heading 3          → sub-block name (optional)
  - Normal             → body text, [IMG: desc], [FORMULA: ...], [ROJO:], [AMARILLO:], [AZUL:]
  - List Bullet/Number → list items
  - Inline image       → automatically extracted to data/input/images/<docname>/
                         followed by [IMG: description] line for the alt-text
"""

import re
import argparse
import json
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

MICROLECCION_RE = re.compile(r"MICROLECCIÓN\s+(\d+)\s*:\s*(.+)", re.IGNORECASE)
IMG_RE          = re.compile(r"\[IMG:\s*(.+?)\]", re.IGNORECASE)
FORMULA_RE      = re.compile(r"\[FORMULA:\s*(.+?)\]", re.IGNORECASE)
COLOR_TAG_RE    = re.compile(r"\[(ROJO|AMARILLO|AZUL):\s*(.+?)\]", re.IGNORECASE)
RID_RE          = re.compile(r'r:embed="([^"]+)"')

_BLIP_TAG = qn("a:blip")


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _build_rid_map(docx_path: Path) -> dict[str, Path]:
    """
    Extract all embedded images from the docx to data/input/images/<stem>/.
    Returns {rId: local_path} for images with content (skips decorative 0-byte files).
    """
    out_dir = docx_path.parent / "images" / docx_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    rid_map: dict[str, Path] = {}
    with zipfile.ZipFile(docx_path) as z:
        try:
            rels_xml = z.read("word/_rels/document.xml.rels").decode()
        except KeyError:
            return rid_map

        for m in re.finditer(r'Id="([^"]+)"[^>]+Target="(media/[^"]+)"', rels_xml):
            rid, target = m.group(1), m.group(2)
            try:
                data = z.read(f"word/{target}")
            except KeyError:
                continue
            if len(data) < 100:          # skip decorative/empty images
                continue
            out_path = out_dir / Path(target).name
            out_path.write_bytes(data)
            rid_map[rid] = out_path

    return rid_map


def _get_rids(para) -> list[str]:
    """Return image rIds referenced in a paragraph's XML."""
    xml = para._element.xml if hasattr(para._element, "xml") else ""
    return RID_RE.findall(xml)


def _has_inline_image(para) -> bool:
    xml = para._element.xml if hasattr(para._element, "xml") else ""
    return _BLIP_TAG in xml or "a:blip" in xml or "v:imagedata" in xml


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _para_style(para) -> str:
    return para.style.name.lower().strip()


def _clean_text(text: str) -> str:
    return text.strip()


def _parse_inline_tags(text: str) -> list[dict]:
    """
    Split text into segments, separating plain text from [ROJO:], [AMARILLO:],
    [AZUL:] emphasis tags.
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


# ---------------------------------------------------------------------------
# Paragraph → element
# ---------------------------------------------------------------------------

def _para_to_element(para, rid_map: dict[str, Path] | None = None) -> dict | None:
    """
    Convert a paragraph to a pipeline element dict, or None to skip.

    Image elements include a 'local_path' when the image was extracted from
    the docx — the uploader uses this path to push the file to Supabase Storage.
    """
    style = _para_style(para)
    text  = _clean_text(para.text)

    # ── Inline image embedded in the paragraph ──────────────────────────────
    if _has_inline_image(para):
        local_path: str | None = None
        if rid_map:
            rids = _get_rids(para)
            for rid in rids:
                if rid in rid_map:
                    local_path = str(rid_map[rid])
                    break
        # Description comes from inline [IMG:] tag in same paragraph, or will
        # be filled in by the lookahead in extract() from the next paragraph.
        img_match = IMG_RE.search(text)
        return {
            "type": "image",
            "description": img_match.group(1).strip() if img_match else "",
            "local_path": local_path,
        }

    # ── [IMG: desc] placeholder line (no actual embedded image) ─────────────
    img_match = IMG_RE.fullmatch(text) if text else None
    if img_match:
        return {"type": "image", "description": img_match.group(1).strip(), "local_path": None}

    # ── [FORMULA: ...] ───────────────────────────────────────────────────────
    formula_match = FORMULA_RE.fullmatch(text) if text else None
    if formula_match:
        return {"type": "formula", "text": formula_match.group(1).strip()}

    # ── List items ───────────────────────────────────────────────────────────
    if "list" in style or para.style.name.startswith("List"):
        if not text:
            return None
        pPr = para._p.pPr
        level = pPr.numPr.ilvl.val if (pPr is not None and pPr.numPr is not None) else 0
        return {"type": "list_item", "text": text, "level": level}

    # ── Normal body text ─────────────────────────────────────────────────────
    if style == "normal" and text:
        return {"type": "paragraph", "segments": _parse_inline_tags(text)}

    return None


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

def extract(docx_path: str | Path) -> dict:
    """
    Parse a standardized .docx and return structured data.

    Embedded images are automatically extracted to
    data/input/images/<docname>/ and referenced via 'local_path' in each
    image element. The uploader uses those paths to push files to Supabase
    Storage and replace them with public URLs.

    Returns:
    {
      "title": "FISIOLOGÍA CELULAR",
      "microlecciones": [
        {
          "numero": 1,
          "titulo": "Membrana celular",
          "bloques": [
            {
              "titulo": "Membrana celular",
              "nivel": 2,
              "elementos": [
                {"type": "paragraph", "segments": [...]},
                {"type": "list_item", "text": "...", "level": 0},
                {"type": "formula", "text": "..."},
                {
                  "type": "image",
                  "description": "Diagrama de la bicapa lipídica",
                  "local_path": "data/input/images/doc/image1.jpg"
                },
              ]
            }
          ]
        }
      ]
    }
    """
    docx_path = Path(docx_path)
    doc       = Document(docx_path)
    rid_map   = _build_rid_map(docx_path)

    result = {"title": "", "microlecciones": []}
    current_microleccion: dict | None = None
    current_bloque: dict | None       = None

    paragraphs = list(doc.paragraphs)
    i = 0

    while i < len(paragraphs):
        para  = paragraphs[i]
        style = _para_style(para)
        text  = _clean_text(para.text)
        i    += 1

        # ── Document title ───────────────────────────────────────────────────
        if style == "title":
            if text:
                result["title"] = text
            continue

        # ── Microlección (Heading 1) ─────────────────────────────────────────
        if style == "heading 1":
            match = MICROLECCION_RE.match(text)
            if match:
                numero = int(match.group(1))
                titulo = match.group(2).strip()
            else:
                numero = len(result["microlecciones"]) + 1
                titulo = text

            current_bloque       = None
            current_microleccion = {"numero": numero, "titulo": titulo, "bloques": []}
            result["microlecciones"].append(current_microleccion)
            continue

        # ── Block (Heading 2) ────────────────────────────────────────────────
        if style == "heading 2":
            if current_microleccion is None:
                current_microleccion = {"numero": 0, "titulo": "", "bloques": []}
                result["microlecciones"].append(current_microleccion)
            current_bloque = {"titulo": text, "nivel": 2, "elementos": []}
            current_microleccion["bloques"].append(current_bloque)
            continue

        # ── Sub-block (Heading 3) ────────────────────────────────────────────
        if style == "heading 3":
            if current_microleccion is None:
                continue
            current_bloque = {"titulo": text, "nivel": 3, "elementos": []}
            current_microleccion["bloques"].append(current_bloque)
            continue

        # ── Body content ─────────────────────────────────────────────────────
        element = _para_to_element(para, rid_map)
        if element is None:
            continue

        # Lookahead: if this is an image without description, check next para
        # for a [IMG: description] line (the standard format places it below).
        if element["type"] == "image" and not element["description"]:
            if i < len(paragraphs):
                next_text = _clean_text(paragraphs[i].text)
                img_match = IMG_RE.fullmatch(next_text) if next_text else None
                if img_match:
                    element["description"] = img_match.group(1).strip()
                    i += 1      # consume the description paragraph

        if current_microleccion is None:
            continue

        if current_bloque is None:
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
    parser.add_argument("--input",  required=True, help="Path to the .docx file")
    parser.add_argument("--output", help="Path to write JSON output (default: stdout)")
    args = parser.parse_args()

    data   = extract(args.input)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
