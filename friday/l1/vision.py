"""L1 primitive: vision (screenshot analysis via OCR and LLM).

Two-tier vision system matching Friday's philosophy:

  extract_text(image_path)
    FREE, LOCAL — Tesseract OCR. Extracts all visible text from an image.
    Handles: error messages, receipts, UI labels, dialog text, terminal
    output. No network, no API key, no cost. Works offline.

  describe(image_path, instruction)
    LLM-BASED — costs ~$0.01 per call. Understands visual content:
    layout, relationships, charts, comparisons. The "LLM-in-primitive
    exception" (same class as gmail.summarize and dev.digest).

Tesseract setup:
  Linux:   pacman -S tesseract
  Windows: winget install UB-Mannheim.TesseractOCR
  macOS:   brew install tesseract

If tesseract is not installed, extract_text raises PrimitiveError with
install instructions. The describe primitive uses dev.run (Claude CLI)
and requires the standard dev environment.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout

TESSERACT_TIMEOUT_S = 30
DEFAULT_LANGUAGE = "eng"

# Free vision models — these run through the local Claude CLI proxy.
# oc/mimo-v2.5-free: good general vision, fast, free
# gemini/gemma-4-31b-it: Google's vision model, free tier
# Override with FRIDAY_VISION_MODEL env var.
VISION_MODELS = ["oc/mimo-v2.5-free", "gemini/gemma-4-31b-it"]
DEFAULT_VISION_MODEL = VISION_MODELS[0]

# Windows: tesseract.exe may be in a non-standard location
_IS_WINDOWS = os.name == "nt"


def _find_tesseract() -> str:
    """Locate the tesseract binary. Returns the command name/path."""
    # Check common locations
    for candidate in ["tesseract", "tesseract.exe"]:
        try:
            proc = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Windows: check common install paths
    if _IS_WINDOWS:
        username = os.environ.get("USERNAME", "")
        for path in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            rf"C:\Users\{username}\AppData\Local\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.isfile(path):
                return path

    raise PrimitiveError(
        "tesseract is not installed or not on PATH. "
        "Install: pacman -S tesseract (Linux) or "
        "winget install UB-Mannheim.TesseractOCR (Windows) "
        "or download from https://github.com/UB-Mannheim/tesseract/wiki",
        state="OCR unavailable",
    )


def _validate_image(image_path: str) -> Path:
    """Validate that the image file exists and is readable."""
    p = Path(image_path)
    if not p.exists():
        raise PreconditionError(f"image file does not exist: {image_path!r}")
    if not p.is_file():
        raise PreconditionError(f"image path is not a file: {image_path!r}")
    # Check file size (reject empty or very large files)
    size = p.stat().st_size
    if size == 0:
        raise PreconditionError(f"image file is empty: {image_path!r}")
    if size > 50 * 1024 * 1024:  # 50 MB
        raise PreconditionError(f"image file too large ({size} bytes, max 50MB)")
    return p


@contract(
    precondition="image_path is an existing, non-empty image file (PNG, JPG, BMP, TIFF, etc.); "
    "tesseract is installed.",
    postcondition="Returns the extracted text from the image. Makes no state changes "
    "except creating a temporary output file (cleaned up).",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing/empty/oversized files or missing tesseract; "
    "PrimitiveError if tesseract fails or times out; PrimitiveTimeout if OCR takes too long.",
    returns="dict: {text: str, confidence: float|None, language: str, word_count: int}.",
)
def extract_text(
    image_path: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    """Extract text from an image using Tesseract OCR (free, local).

    Returns a dict with the extracted text, optional confidence score,
    language used, and word count. The text is the raw OCR output —
    no post-processing, no LLM involved.

    Args:
        image_path: Path to the image file (PNG, JPG, BMP, TIFF, etc.)
        language: Tesseract language code (default: 'eng'). Multiple
                  languages: 'eng+hin' (requires both trained data sets).
    """
    _validate_image(image_path)
    tesseract = _find_tesseract()

    if not language or not language.strip():
        language = DEFAULT_LANGUAGE

    # Tesseract outputs to stdout with -l <lang> <image> stdout
    try:
        proc = subprocess.run(
            [tesseract, image_path, "stdout", "-l", language.strip()],
            capture_output=True,
            text=True,
            timeout=TESSERACT_TIMEOUT_S,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "tesseract binary not found at expected path",
            state="OCR unavailable",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveTimeout(
            f"tesseract timed out after {TESSERACT_TIMEOUT_S}s on {image_path!r}",
            state="OCR incomplete",
        ) from exc

    if proc.returncode != 0:
        stderr = proc.stderr.strip()[:300] if proc.stderr else "unknown error"
        raise PrimitiveError(
            f"tesseract failed (rc={proc.returncode}): {stderr}",
            state="OCR failed",
        )

    text = proc.stdout.strip()
    words = text.split() if text else []

    return {
        "text": text,
        "confidence": None,  # tesseract stdout mode doesn't provide confidence
        "language": language,
        "word_count": len(words),
    }


def _find_claude() -> str:
    """Locate the claude CLI binary. Tries common locations on Windows."""
    import shutil

    # Check PATH first
    found = shutil.which("claude")
    if found:
        return found

    # Windows: check common npm global install locations
    if _IS_WINDOWS:
        for path in [
            os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
            os.path.expandvars(r"%APPDATA%\npm\claude"),
        ]:
            if os.path.isfile(path):
                return path

    # Fall back to just "claude" and let subprocess find it
    return "claude"


def _encode_image_base64(image_path: str) -> str:
    """Read an image file and return its base64-encoded content."""
    import base64

    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii")


def _call_vision_model(
    prompt: str,
    image_path: str,
    model: str,
    timeout_s: int = 60,
) -> str:
    """Call a vision model via claude -p with the image as context.

    The image is base64-encoded and included in the prompt text so the
    model can actually see it. We try the primary model first, then
    fall back to alternatives.
    """
    import json as _json

    # Encode the image as base64 so the model can see it
    b64 = _encode_image_base64(image_path)
    # Determine mime type from extension
    ext = Path(image_path).suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/png")

    # Build the full prompt with embedded image data
    full_prompt = (
        f"Analyze this image.\n\n"
        f"{prompt}\n\n"
        f"[Image data: {mime}; base64 length: {len(b64)} chars]\n"
        f"{b64}\n"
        "Respond with ONLY the analysis text. No preamble — just the answer."
    )

    claude_bin = _find_claude()
    cmd = [
        claude_bin, "-p", "-",
        "--output-format", "json",
        "--model", model,
    ]
    # Permission bypass: vision.describe needs to read image files.
    if os.environ.get("FRIDAY_ALLOW_DANGEROUS") == "1":
        cmd += ["--permission-mode", "bypassPermissions"]

    try:
        proc = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            f"claude CLI not found at {claude_bin} — install Claude Code CLI",
            state="vision unavailable",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveTimeout(
            f"vision model {model} timed out after {timeout_s}s",
            state="analysis not produced",
        ) from exc

    if proc.returncode != 0:
        raise PrimitiveError(
            f"vision model {model} failed (rc={proc.returncode}): {proc.stderr.strip()[:300]}",
            state="analysis not produced",
        )

    try:
        result = _json.loads(proc.stdout)
        text = result.get("result", "")
    except (_json.JSONDecodeError, ValueError):
        text = proc.stdout.strip()

    return str(text)


@contract(
    precondition="image_path is an existing, non-empty image file; "
    "instruction is a non-empty string describing what to extract/describe; "
    "the Claude CLI is available; FRIDAY_ALLOW_DANGEROUS=1 is recommended "
    "for permission bypass (otherwise the model may ask for file access permission).",
    postcondition="Returns the LLM's analysis of the image.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for missing/empty files or empty instruction; "
    "PrimitiveError if the LLM call fails.",
    returns="str: the LLM's description/analysis of the image.",
)
def describe(
    image_path: str,
    instruction: str = "Describe what you see in this image in detail.",
    model: str | None = None,
) -> str:
    """Analyze an image using a free vision model.

    Uses oc/mimo-v2.5-free (or FRIDAY_VISION_MODEL override) — FREE,
    no API key needed, runs through the local Claude CLI proxy.

    The LLM can understand visual content: layout, relationships,
    charts, error messages in context, UI state, etc.

    For simple text extraction, use extract_text (free, local OCR)
    instead — it's faster and costs nothing.

    Args:
        image_path: Path to the image file.
        instruction: What to look for or describe. Be specific for
                     better results (e.g. "extract the error message"
                     or "what is the total amount on this receipt?").
        model: Override the vision model. Default: FRIDAY_VISION_MODEL
               env var, or oc/mimo-v2.5-free.
    """
    _validate_image(image_path)

    if not instruction or not instruction.strip():
        raise PreconditionError("describe requires a non-empty instruction")

    target_model = (
        model
        or os.environ.get("FRIDAY_VISION_MODEL")
        or DEFAULT_VISION_MODEL
    )

    # Build a prompt with the instruction (image is embedded by _call_vision_model)
    prompt = instruction.strip()

    # Try primary model, fall back to alternatives
    last_error = None
    models_to_try = [target_model] + [m for m in VISION_MODELS if m != target_model]

    for m in models_to_try:
        try:
            text = _call_vision_model(prompt, image_path, m, timeout_s=60)
            if text.strip():
                return text
        except (PrimitiveError, PrimitiveTimeout) as exc:
            last_error = exc
            continue

    # All models failed
    raise PrimitiveError(
        f"all vision models failed; last error: {last_error}",
        state="analysis not produced",
    )
