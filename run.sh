#!/usr/bin/env bash
# run.sh — Manual trigger for the Humpy autocontent pipeline.
#
# Usage:
#   ./run.sh documento.docx
#   ./run.sh documento.docx --questions 3
#   ./run.sh documento.docx --dry-run
#   ./run.sh --help

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Help ────────────────────────────────────────────────────────────────────
usage() {
  echo -e "${BOLD}Humpy Autocontent Pipeline${NC}"
  echo ""
  echo -e "  ${CYAN}./run.sh <archivo.docx> [opciones]${NC}"
  echo ""
  echo "Opciones:"
  echo "  --questions N    Preguntas de quiz por microlección (default: 5)"
  echo "  --dry-run        Procesa el documento pero NO sube a Supabase"
  echo "  --skip-upload    Igual que --dry-run"
  echo "  --help           Muestra este mensaje"
  echo ""
  echo "Ejemplos:"
  echo "  ./run.sh data/input/modulo1.docx"
  echo "  ./run.sh data/input/modulo1.docx --questions 3"
  echo "  ./run.sh data/input/modulo1.docx --dry-run"
  exit 0
}

# ── Parse args ───────────────────────────────────────────────────────────────
if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  usage
fi

DOCX="$1"; shift
EXTRA_ARGS=("$@")

# ── Validate input file ───────────────────────────────────────────────────────
if [[ ! -f "$DOCX" ]]; then
  # Try looking inside data/input/ as a convenience
  if [[ -f "data/input/$DOCX" ]]; then
    DOCX="data/input/$DOCX"
  else
    echo -e "${RED}ERROR: No se encontró el archivo: $DOCX${NC}" >&2
    echo "  Coloca el archivo en data/input/ o proporciona la ruta completa." >&2
    exit 1
  fi
fi

# ── Check .env ────────────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  echo -e "${YELLOW}ADVERTENCIA: No se encontró el archivo .env${NC}"
  echo "  Copia env.example a .env y completa las variables antes de correr el pipeline."
  echo ""
fi

# ── Check Python venv ─────────────────────────────────────────────────────────
if [[ -d ".venv" ]]; then
  source .venv/bin/activate
elif [[ -d "venv" ]]; then
  source venv/bin/activate
fi

# ── Run ───────────────────────────────────────────────────────────────────────
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BASENAME=$(basename "$DOCX" .docx)
OUTPUT_DIR="data/output/${BASENAME}_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Humpy Autocontent Pipeline${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Archivo:  ${CYAN}$DOCX${NC}"
echo -e "  Output:   ${CYAN}$OUTPUT_DIR/${NC}"
echo ""

python -m src.pipeline \
  --input "$DOCX" \
  --extracted-output "$OUTPUT_DIR/extracted.json" \
  --generated-output "$OUTPUT_DIR/generated.json" \
  --upload-report    "$OUTPUT_DIR/upload_report.json" \
  "${EXTRA_ARGS[@]}"

EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}✓ Pipeline completado.${NC}"
  echo -e "  Resultados guardados en: ${CYAN}$OUTPUT_DIR/${NC}"
else
  echo -e "${RED}${BOLD}✗ Pipeline falló (código $EXIT_CODE).${NC}"
  echo "  Revisa los errores arriba."
fi

exit $EXIT_CODE
