# Humpy Autocontent Pipeline

Pipeline de automatización de contenido educativo para la plataforma Humpy. Convierte documentos Word en microlecciones HTML y preguntas de quiz usando Claude API, con una etapa de revisión humana en Supabase antes de publicar.

---

## Flujo del pipeline

```
.docx
  │
  ├─ extractor.py      Lee estilos de Word → JSON estructurado
  │                    Extrae imágenes embebidas → data/input/images/<doc>/
  │
  ├─ generator.py      Claude API (claude-opus-4-8)
  │                    Paso 1: genera HTML semántico por microlección
  │                    Paso 2: genera quiz con niveles de Bloom
  │
  ├─ validator.py      Valida esquema del JSON generado        (próximamente)
  │
  ├─ uploader.py       Sube imágenes a Supabase Storage
  │                    Reemplaza PLACEHOLDERs con URLs reales
  │                    Inserta en staging_microlecciones + staging_preguntas
  │
  └─ [Revisión humana en Supabase]
       Aprueba / rechaza → publicación en Humpy
```

---

## Estructura del repositorio

```
src/
  extractor.py          Parsea .docx → JSON estructurado + extrae imágenes
  generator.py          Genera HTML + quiz con Claude API
  validator.py          Valida JSON del generator            (próximamente)
  uploader.py           Sube a Supabase Storage y staging tables
  pipeline.py           Orquestador end-to-end               (próximamente)

scripts/
  reformat_docx.py              Convierte docs legacy al formato estándar
  reformat_sistema_nervioso.py  Ejemplo: extrae imágenes de tablas con Claude Vision

tests/
  test_extractor.py     14 tests (estructura, imágenes, inline tags)
  test_generator.py     11 tests (prompts, parsing, pipeline completo)
  test_validator.py     Placeholder

docs/
  formato-contenido.md  Estándar de formato Word para creadores de contenido

data/
  input/                .docx a procesar (excluidos del repo)
  input/images/         Imágenes extraídas automáticamente por el extractor
  output/               JSONs generados (excluidos del repo)

sql/
  staging_tables.sql    Esquema de tablas staging en Supabase  (próximamente)
```

---

## Instalación

```bash
git clone https://github.com/humpy-consultores/Humpy_autocontent_pipeline.git
cd Humpy_autocontent_pipeline

python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt

cp .env.example .env
# Editar .env con las credenciales reales
```

---

## Variables de entorno

```env
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu_service_role_key
```

---

## Uso

### Correr el pipeline completo (manual por etapas)

```bash
# 1. Extraer contenido del Word (también extrae imágenes automáticamente)
python src/extractor.py --input data/input/documento.docx --output data/output/extracted.json

# 2. Generar HTML + quiz con Claude API
python src/generator.py --input data/output/extracted.json --output data/output/generated.json --questions 5

# 3. Subir a Supabase staging (sube imágenes + inserta registros)
python src/uploader.py --generated data/output/generated.json --extracted data/output/extracted.json
```

### Correr tests

```bash
python -m pytest tests/ -v
```

---

## Formato del documento Word

Los documentos deben seguir el estándar definido en [`docs/formato-contenido.md`](docs/formato-contenido.md).

Resumen de estilos requeridos:

| Elemento | Estilo Word |
|---|---|
| Título del curso | `Title` |
| Microlección | `Heading 1` — formato: `MICROLECCIÓN N: Título` |
| Bloque temático | `Heading 2` |
| Subbloque | `Heading 3` (opcional) |
| Cuerpo de texto | `Normal` |
| Listas | Viñetas / Numeración de Word |
| Imagen inline | Insertar inline + línea `[IMG: descripción]` debajo |
| Fórmulas | `[FORMULA: expresión]` |
| Énfasis | `[ROJO: texto]`, `[AMARILLO: texto]`, `[AZUL: texto]` |

### Imágenes

El extractor detecta automáticamente las imágenes embebidas en el documento, las guarda en `data/input/images/<nombre_doc>/` y las referencia con `local_path` en el JSON. El uploader las sube a Supabase Storage y reemplaza los `PLACEHOLDER` en el HTML con las URLs reales.

No es necesario hacer nada manualmente — solo insertar la imagen inline en Word y escribir `[IMG: descripción]` en el párrafo siguiente.

---

## Output del generator

```json
{
  "title": "FISIOLOGÍA CELULAR",
  "microlecciones": [
    {
      "numero": 1,
      "titulo": "Membrana celular",
      "html": "<section>...</section>",
      "quiz": {
        "preguntas": [
          {
            "nivel_bloom": "recordar",
            "enunciado": "¿Cuál es la función principal de la membrana celular?",
            "opciones": {"a": "...", "b": "...", "c": "...", "d": "..."},
            "respuesta_correcta": "b",
            "explicacion": "La membrana delimita y protege la célula."
          }
        ]
      }
    }
  ]
}
```

---

## Tablas de Supabase

El uploader inserta en tablas de **staging** — el contenido no se publica directamente:

| Tabla | Descripción |
|---|---|
| `documentos` | Registro de cada .docx procesado |
| `staging_microlecciones` | HTML generado, pendiente de aprobación |
| `staging_preguntas` | Quiz generado, pendiente de aprobación |
| `microlecciones` | Producción — solo contenido aprobado |
| `preguntas` | Producción — solo contenido aprobado |

---

## Estado del proyecto

| Módulo | Estado |
|---|---|
| `src/extractor.py` | ✅ Completo — 14 tests |
| `src/generator.py` | ✅ Completo — 11 tests |
| `src/uploader.py` | ✅ Implementado |
| `src/validator.py` | 🔄 En desarrollo |
| `src/pipeline.py` | 🔄 Pendiente |
| `sql/staging_tables.sql` | 🔄 Pendiente |

---

## Stack

- **Python 3.10+**
- [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) — Claude API (`claude-opus-4-8`)
- [`supabase`](https://github.com/supabase-community/supabase-py) — base de datos y storage
- [`python-docx`](https://python-docx.readthedocs.io/) — lectura de documentos Word
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — variables de entorno
- [`pytest`](https://pytest.org/) — testing
