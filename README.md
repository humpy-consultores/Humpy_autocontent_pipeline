# Humpy Content Pipeline

Pipeline de automatización de contenido educativo para la plataforma Humpy. Convierte material académico en Word (.docx) en microlecciones y quizzes usando Python y Claude API, validando el contenido en tablas staging antes de publicarlo.

---

## Objetivo

Automatizar la conversión de material académico en microlecciones y preguntas de quiz, con una etapa de revisión intermedia antes de publicar en las tablas activas de la app.

```
Documento Word (.docx)
        |
  Extracción de texto por secciones
        |
  Limpieza y estructuración
        |
  Generación de microlecciones + preguntas (Claude API)
        |
  Tablas staging (revisión antes de publicar)
        |
  Publicación en Humpy
```

---

## Estructura del repositorio

```
humpy-content-pipeline/
|
├── src/                         # Scripts Python del pipeline
│   ├── extractor.py             # Lectura y extracción del Word por secciones
│   ├── cleaner.py               # Limpieza y normalización del texto extraído
│   ├── generator.py             # Generación de microlecciones y preguntas con Claude API
│   ├── validator.py             # Validación y limpieza del JSON generado
│   ├── uploader.py              # Inserción en tablas staging de Supabase
│   └── pipeline.py              # Script principal que orquesta todo el flujo
│
├── sql/                         # Scripts SQL para Supabase
│   ├── staging_tables.sql       # Creación de tablas staging
│   └── views.sql                # Vistas para revisión de contenido antes de publicar
│
├── docs/                        # Documentación del proyecto
│   ├── architecture.md          # Diagrama y decisiones de arquitectura
│   ├── supabase-schema.md       # Esquema de tablas relevantes
│   └── prompt-design.md         # Diseño y versiones de prompts usados
│
├── notebooks/                   # Pruebas y demos por etapa del pipeline
│   ├── 01_extraccion.ipynb
│   ├── 02_generacion.ipynb
│   └── 03_staging.ipynb
│
├── data/
│   └── samples/                 # Archivos de ejemplo para pruebas (no datos reales)
│
├── .env.example                 # Variables de entorno requeridas (sin valores reales)
├── .gitignore                   # Archivos excluidos del repositorio
├── requirements.txt             # Dependencias de Python
└── README.md                    # Este archivo
```

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/humpy-content-pipeline.git
cd humpy-content-pipeline
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Edita el archivo .env con tus credenciales reales
```

---

## Variables de entorno requeridas

Crea un archivo `.env` en la raíz del proyecto con estos valores:

```env
ANTHROPIC_API_KEY=tu_api_key_de_claude
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu_service_role_key
```

IMPORTANTE: Nunca subas el archivo `.env` al repositorio. Ya está incluido en `.gitignore`.

---

## Uso

### Procesar un solo documento

```bash
python src/pipeline.py --input data/samples/mi_documento.docx
```

### Procesar múltiples documentos en lote

```bash
python src/pipeline.py --input data/samples/ --batch
```

### Solo extraer texto (sin generar preguntas)

```bash
python src/extractor.py --input data/samples/mi_documento.docx
```

---

## Formato de output (JSON)

Cada pregunta generada sigue esta estructura antes de insertarse en staging:

```json
{
  "pregunta": "¿Cuál es el objetivo principal del proceso de CIP?",
  "tipo": "opcion_multiple",
  "dificultad": "media",
  "bloom": "comprender",
  "opciones": [
    { "texto": "Limpiar los equipos de producción", "correcta": true },
    { "texto": "Aumentar la velocidad de la línea", "correcta": false },
    { "texto": "Reducir el tiempo de cambio", "correcta": false },
    { "texto": "Calibrar los sensores", "correcta": false }
  ]
}
```

---

## Tablas staging

Las preguntas y microlecciones generadas no se publican directamente. Primero se insertan en tablas staging donde pueden ser revisadas y aprobadas manualmente antes de llegar a los usuarios. Los scripts SQL para crear estas tablas están en la carpeta `sql/`.

---

## Dependencias principales

| Librería | Uso |
|---|---|
| `python-docx` | Lectura y extracción del documento Word |
| `anthropic` | Conexión con Claude API para generación de contenido |
| `supabase` | Inserción de preguntas en la base de datos |
| `python-dotenv` | Manejo de variables de entorno |

---

## Cómo contribuir

1. Crea una rama con el nombre de tu feature: `git checkout -b feature/nombre-feature`
2. Haz tus cambios y escribe tests si aplica
3. Abre un Pull Request describiendo qué cambiaste y por qué
4. Espera revisión antes de hacer merge a `main`

### Convenciones de nombres de ramas

| Tipo | Prefijo | Ejemplo |
|---|---|---|
| Nueva funcionalidad | `feature/` | `feature/validacion-preguntas` |
| Corrección de bug | `fix/` | `fix/encoding-caracteres` |
| Documentación | `docs/` | `docs/actualizar-readme` |
| Pruebas | `test/` | `test/extractor-tablas` |

---

## Backlog

El backlog del proyecto está gestionado en GitHub Projects de este repositorio.

| Fase | Estado |
|---|---|
| Fase 1 — Definición del input y estructura de documentos | Completado |
| Fase 2 — Extracción y limpieza de contenido | Pendiente |
| Fase 3 — Generación de microlecciones y preguntas | Pendiente |
| Fase 4 — Validación del output JSON | Pendiente |
| Fase 5 — Integración con tablas staging de Supabase | Pendiente |
| Fase 6 — Revisión manual y publicación | Pendiente |
| Fase 7 — Automatización en lote y logs | Pendiente |

---

## Equipo

| Rol | Responsabilidad |
|---|---|
| PM / Dev | Arquitectura del pipeline, integración API |
| Dev plataforma | Schema Supabase, tablas staging, entorno de pruebas |
| Encargado de contenido | Validación de documentos de entrada y calidad de preguntas |
