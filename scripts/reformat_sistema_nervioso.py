"""
Reformatea SISTEMA_NERVIOSO.docx al formato estándar del pipeline.

Pasos:
1. Extrae imágenes embebidas en tablas → data/input/images/
2. Llama a Claude Vision para describir cada imagen automáticamente
3. Genera el .docx reformateado con:
   - Heading 1: MICROLECCIÓN 1: Sistema Nervioso y Presión Arterial
   - Heading 2: secciones principales (tablas de layout)
   - Heading 3: subsecciones (Heading 3 del original)
   - Normal: cuerpo de texto
   - [IMG: descripción auto-generada]: placeholder por imagen
"""

import re
import os
import base64
import zipfile
from pathlib import Path
from lxml import etree
from docx import Document
import anthropic

ROOT    = Path(__file__).resolve().parent.parent
INPUT   = ROOT / "data/input/SISTEMA_NERVIOSO.docx"
OUTPUT  = ROOT / "data/input/SISTEMA_NERVIOSO_FORMATO.docx"
IMG_DIR = ROOT / "data/input/images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "claude-opus-4-8"

# ---------------------------------------------------------------------------
# Paso 1 — Extraer imágenes del docx y mapear rId → path local
# ---------------------------------------------------------------------------

def extract_images(docx_path: Path) -> dict:
    """Extrae word/media/* y devuelve {rId: Path}."""
    rid_map = {}
    with zipfile.ZipFile(docx_path) as z:
        # Parsear relationships
        rels_xml = z.read("word/_rels/document.xml.rels").decode()
        for m in re.finditer(r'Id="([^"]+)"[^>]+Target="(media/[^"]+)"', rels_xml):
            rid, target = m.group(1), m.group(2)
            filename = Path(target).name
            out_path = IMG_DIR / filename
            data = z.read(f"word/{target}")
            out_path.write_bytes(data)
            rid_map[rid] = out_path
            print(f"  Extraída: {filename} ({len(data)//1024} KB) ← {rid}")
    return rid_map


# ---------------------------------------------------------------------------
# Paso 2 — Describir imágenes con Claude Vision
# ---------------------------------------------------------------------------

def describe_image(client: anthropic.Anthropic, img_path: Path) -> str:
    """Envía la imagen a Claude y pide una descripción educativa breve."""
    suffix = img_path.suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                      ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/jpeg")

    data = img_path.read_bytes()
    if len(data) < 100:          # imagen vacía o corrupta
        return f"Diagrama relacionado con {img_path.stem}"

    b64 = base64.standard_b64encode(data).decode()

    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Describe esta imagen en una frase corta (máximo 15 palabras) "
                        "adecuada como texto alternativo educativo en español. "
                        "Solo la descripción, sin puntuación final."
                    ),
                },
            ],
        }],
    )
    return response.content[0].text.strip().rstrip(".")


# ---------------------------------------------------------------------------
# Paso 3 — Helpers de clasificación de texto
# ---------------------------------------------------------------------------

SECTION_TITLES_RE = re.compile(
    r"^(sistema nervioso|los barorreceptores|núcleo del tracto solitario|"
    r"sistema simpático|quimiorreceptores|sistema renina|calicreína|"
    r"péptido natriurético|mecanismos reflejos|mecanismo)",
    re.IGNORECASE,
)

def classify_text(text: str):
    """Devuelve ('heading2'|'heading3'|'normal'|'list', text)."""
    t = text.strip()
    if not t:
        return None, None

    # Sección numerada tipo "1. LOS BARORRECEPTORES" o encabezado corto
    if re.match(r"^\d+\.\s+[A-ZÁÉÍÓÚÑ\s]{4,}$", t):
        clean = re.sub(r"^\d+\.\s+", "", t).title()
        return "heading2", clean

    if SECTION_TITLES_RE.match(t) and len(t) < 80:
        return "heading2", t.title()

    # Listas: líneas cortas sin punto final
    if len(t) < 100 and not t.endswith(".") and "\n" not in t:
        return "list", t

    return "normal", t


def get_rids_in_cell(cell_element) -> list:
    xml = etree.tostring(cell_element, encoding="unicode")
    return re.findall(r'r:embed="([^"]+)"', xml)


# ---------------------------------------------------------------------------
# Paso 4 — Reformatear
# ---------------------------------------------------------------------------

def reformat(api_key: str | None = None):
    print("Extrayendo imágenes...")
    rid_map = extract_images(INPUT)

    print("Describiendo imágenes con Claude Vision...")
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    rid_desc: dict[str, str] = {}
    for rid, path in rid_map.items():
        desc = describe_image(client, path)
        rid_desc[rid] = desc
        print(f"  {rid}: {desc}")

    # Filtrar el rId de la imagen decorativa/vacía (image4.png = 0 KB)
    decorative_rids = {rid for rid, path in rid_map.items() if path.stat().st_size < 200}

    print("\nGenerando documento reformateado...")
    src = Document(INPUT)
    dst = Document()

    # Título del curso
    dst.add_heading("FISIOLOGÍA CARDIOVASCULAR", level=0)
    # Una microlección que envuelve todo el documento
    dst.add_heading("MICROLECCIÓN 1: Mecanismos que regulan la Presión Arterial – Sistema Nervioso", level=1)

    # Párrafos iniciales (intro, temas)
    for para in src.paragraphs:
        text = para.text.strip()
        style = para.style.name.lower()
        if not text:
            continue

        # Saltar el título redundante del Heading 2 "Presión arterial"
        if "presión arterial" == text.lower() and "heading" in style:
            continue

        # Saltar la línea "MICROLECCIÓN 2: ..." del original (ya la pusimos como Heading 1)
        if text.upper().startswith("MICROLECCIÓN"):
            continue

        # Subtítulos de los sistemas en la intro → lista
        if style == "normal" and len(text) < 120:
            dst.add_paragraph(text, style="List Bullet")
        elif "heading 3" in style:
            dst.add_heading(text, level=3)
        else:
            dst.add_paragraph(text, style="Normal")

    # Tablas (contienen el contenido principal + imágenes)
    seen_rids: set = set()

    for table in src.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_xml = etree.tostring(cell._element, encoding="unicode")
                cell_rids = [r for r in re.findall(r'r:embed="([^"]+)"', cell_xml)
                             if r not in decorative_rids]
                text = cell.text.strip()

                if not text and not cell_rids:
                    continue

                # Clasificar el texto
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                if not lines and not cell_rids:
                    continue

                first_line = lines[0] if lines else ""
                kind, clean_first = classify_text(first_line)

                if kind == "heading2":
                    dst.add_heading(clean_first, level=2)
                    rest = lines[1:]
                elif kind == "heading3":
                    dst.add_heading(clean_first, level=3)
                    rest = lines[1:]
                else:
                    rest = lines

                # Resto de líneas de la celda
                for line in rest:
                    k, t = classify_text(line)
                    if k == "list":
                        dst.add_paragraph(t, style="List Bullet")
                    elif k in ("normal", "heading3"):
                        dst.add_paragraph(t, style="Normal")

                # Insertar placeholders de imagen (solo la primera vez por rId)
                for rid in cell_rids:
                    if rid not in seen_rids:
                        seen_rids.add(rid)
                        desc = rid_desc.get(rid, "Diagrama del sistema nervioso")
                        dst.add_paragraph(f"[IMG: {desc}]", style="Normal")
                        print(f"  → Placeholder insertado: [IMG: {desc}]")

    dst.save(OUTPUT)
    print(f"\nGuardado: {OUTPUT}")


if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANTHROPIC_API_KEY")
    reformat(api_key=key)
