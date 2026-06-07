# CLAUDE.md — Humpy Autocontent Pipeline

Contexto del proyecto para sesiones de Claude Code.

## Objetivo

Pipeline que convierte documentos Word (.docx) en microlecciones y preguntas de quiz para la plataforma Humpy. Usa Claude API para la generación de contenido y Supabase como base de datos, con una etapa de staging obligatoria antes de publicar.

## Flujo del pipeline

```
.docx → extractor → cleaner → generator (Claude API) → validator → uploader (Supabase staging) → revisión humana → publicación
```

## Estructura del proyecto

```
src/           # Módulos del pipeline (en desarrollo)
tests/         # Tests unitarios con pytest
sql/           # Schemas y vistas de Supabase
docs/          # Documentación de arquitectura y prompts
notebooks/     # Jupyter notebooks por etapa del pipeline
data/
  input/       # Documentos Word a procesar
  output/      # JSONs generados
  samples/     # Archivos de ejemplo para pruebas
```

## Comandos frecuentes

```bash
# Instalar dependencias
pip install -r requirements.txt

# Correr el pipeline completo
python src/pipeline.py --input data/input/documento.docx

# Correr tests
pytest tests/

# Solo extracción
python src/extractor.py --input data/input/documento.docx
```

## Variables de entorno requeridas

Copiar `env.example` a `.env` y completar:

```
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
```

## Convenciones

- Idioma del código: inglés (variables, funciones, comentarios)
- Idioma del contenido generado: español
- Ramas: `feature/`, `fix/`, `docs/`, `test/` según tipo
- Tests: usar `pytest`, un archivo por módulo (`test_extractor.py`, etc.)
- El output JSON de cada módulo debe ser validado antes de pasar al siguiente

## Stack

- Python 3.10+
- `anthropic` — Claude API
- `supabase` — base de datos y autenticación
- `python-docx` — lectura de documentos Word
- `python-dotenv` — variables de entorno
- `pytest` — testing
