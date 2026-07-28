"""
Pipeline: end-to-end orchestrator for the Humpy autocontent pipeline.

Flow:
  1. extractor  — parse .docx → structured JSON (also extracts images to disk)
  2. generator  — call Claude API → HTML + quiz JSON
  3. validator  — verify schema before touching Supabase
  4. uploader   — upload images to Storage, insert into staging tables

Usage:
  python src/pipeline.py --input data/input/documento.docx

Optional flags:
  --questions N          Quiz questions per microlección (default: 5)
  --extracted-output     Save extractor JSON to this path
  --generated-output     Save generator JSON to this path
  --upload-report        Save upload report JSON to this path
  --skip-upload          Run extractor + generator + validator only (no Supabase)
  --dry-run              Alias for --skip-upload
"""

import argparse
import json
import sys
import time
from pathlib import Path

from src.extractor  import extract
from src.generator  import generate
from src.validator  import validate, ValidationError


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _log(step: str, msg: str) -> None:
    print(f"[{step}] {msg}", flush=True)


def _log_errors(errors: list[str]) -> None:
    for e in errors:
        print(f"       - {e}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(
    docx_path: str | Path,
    n_questions: int = 5,
    skip_upload: bool = False,
    extracted_output: str | None = None,
    generated_output: str | None = None,
    upload_report_output: str | None = None,
) -> dict:
    """
    Run the full pipeline on a .docx file.

    Returns:
        {
          "extracted":     dict,
          "generated":     dict,
          "validation_ok": bool,
          "upload_report": dict | None   (None when skip_upload=True)
        }
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"Input file not found: {docx_path}")

    # ── Step 1: Extract ──────────────────────────────────────────────────────
    _log("extractor", f"Parsing {docx_path.name} …")
    t0 = time.time()
    extracted = extract(docx_path)
    ml_count = len(extracted.get("microlecciones", []))
    _log("extractor", f"Done — {ml_count} microlección(es) found  ({time.time()-t0:.1f}s)")

    if extracted_output:
        Path(extracted_output).write_text(
            json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _log("extractor", f"Saved to {extracted_output}")

    if ml_count == 0:
        _log("extractor", "WARNING: no microlecciones found — check document formatting.")

    # ── Step 2: Generate ─────────────────────────────────────────────────────
    _log("generator", f"Calling Claude API ({n_questions} questions per microlección) …")
    t0 = time.time()
    generated = generate(extracted, n_questions=n_questions)
    _log("generator", f"Done  ({time.time()-t0:.1f}s)")

    if generated_output:
        Path(generated_output).write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _log("generator", f"Saved to {generated_output}")

    # ── Step 3: Validate ─────────────────────────────────────────────────────
    _log("validator", "Checking output schema …")
    errors = validate(generated)
    if errors:
        _log("validator", f"FAILED — {len(errors)} error(s):")
        _log_errors(errors)
        raise ValidationError(errors)

    total_q = sum(
        len(ml.get("quiz", {}).get("preguntas", []))
        for ml in generated.get("microlecciones", [])
    )
    _log("validator", f"OK — {ml_count} microlección(es), {total_q} pregunta(s)")

    # ── Step 4: Upload ───────────────────────────────────────────────────────
    upload_report = None

    if skip_upload:
        _log("uploader", "Skipped (--skip-upload / --dry-run)")
    else:
        from src.uploader import upload  # lazy import — supabase not needed unless uploading
        _log("uploader", "Uploading images and inserting staging records …")
        t0 = time.time()
        upload_report = upload(generated, extracted)
        subidas = len(upload_report.get("microlecciones_subidas", []))
        _log("uploader", f"Done — {subidas} microlección(es) en staging  ({time.time()-t0:.1f}s)")
        _log("uploader", f"documento_id: {upload_report['documento_id']}")

        if upload_report_output:
            Path(upload_report_output).write_text(
                json.dumps(upload_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _log("uploader", f"Report saved to {upload_report_output}")

    return {
        "extracted":     extracted,
        "generated":     generated,
        "validation_ok": True,
        "upload_report": upload_report,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the Humpy autocontent pipeline end-to-end.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input",            required=True,      help="Path to .docx file")
    parser.add_argument("--questions",        type=int, default=5, help="Quiz questions per microlección")
    parser.add_argument("--skip-upload",      action="store_true", help="Skip Supabase upload")
    parser.add_argument("--dry-run",          action="store_true", help="Alias for --skip-upload")
    parser.add_argument("--extracted-output", help="Save extractor JSON to this path")
    parser.add_argument("--generated-output", help="Save generator JSON to this path")
    parser.add_argument("--upload-report",    help="Save upload report JSON to this path")
    args = parser.parse_args()

    try:
        run(
            docx_path            = args.input,
            n_questions          = args.questions,
            skip_upload          = args.skip_upload or args.dry_run,
            extracted_output     = args.extracted_output,
            generated_output     = args.generated_output,
            upload_report_output = args.upload_report,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    except ValidationError:
        print("Pipeline aborted: fix the errors above and re-run.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
