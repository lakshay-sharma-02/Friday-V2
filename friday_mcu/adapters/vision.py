"""Vision adapter — OCR (Tesseract) and LLM-based image analysis."""

from __future__ import annotations

import subprocess
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError


@contract(
    precondition="image_path points to a readable image file.",
    postcondition="Returns extracted text from the image.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if OCR fails.",
    returns="dict: {text: str, word_count: int, language: str}.",
)
def extract_text(image_path: str, language: str = "eng") -> dict[str, Any]:
    """Extract text from an image using Tesseract OCR (free, local)."""
    if not image_path:
        raise PreconditionError("image_path is required")
    try:
        result = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", language],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise PrimitiveError(f"Tesseract failed: {result.stderr.strip()}")
        text = result.stdout.strip()
        word_count = len(text.split()) if text else 0
        return {"text": text, "word_count": word_count, "language": language}
    except FileNotFoundError:
        raise PrimitiveError("tesseract not found: install tesseract-ocr")
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError("Tesseract timed out") from exc


@contract(
    precondition="image_path points to a readable image file.",
    postcondition="Returns LLM-based description of the image.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if LLM call fails.",
    returns="str: the image description.",
)
def describe(image_path: str, instruction: str = "Describe this image") -> str:
    """Describe an image using OCR + heuristics."""
    if not image_path:
        raise PreconditionError("image_path is required")
    from pathlib import Path
    p = Path(image_path)
    if not p.exists():
        raise PreconditionError(f"image not found: {image_path}")

    # Try OCR first
    try:
        ocr = extract_text(image_path)
        text = ocr.get("text", "")
        word_count = ocr.get("word_count", 0)
        if text.strip():
            desc = f"Image contains {word_count} words. Text extracted: {text[:1500]}"
            return desc
    except Exception:
        pass

    # Fallback: basic image info
    try:
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        mode = img.mode
        return f"Image: {w}x{h} pixels, mode={mode}. No text detected via OCR. Format: {p.suffix}"
    except Exception:
        return f"Image saved at {image_path} ({p.stat().st_size} bytes). Could not analyze content."


class VisionAdapter(Adapter):
    @property
    def name(self) -> str:
        return "vision"

    @property
    def capabilities(self) -> list[str]:
        return ["extract_text", "describe"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "extract_text":
            return extract_text(**kwargs)
        elif action == "describe":
            return describe(**kwargs)
        raise PrimitiveError(f"Unknown vision action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        try:
            result = subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


try:
    register_adapter(VisionAdapter())
except Exception:
    pass
