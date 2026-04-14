from __future__ import annotations

import io
import shutil
from typing import Any

from PIL import Image, ImageOps

from config.settings import settings

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None


class OCRService:
    def __init__(self) -> None:
        if pytesseract is not None and settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def available(self) -> bool:
        if pytesseract is None:
            return False
        if settings.TESSERACT_CMD:
            return True
        return shutil.which("tesseract") is not None

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        enhanced = ImageOps.autocontrast(grayscale)
        return enhanced.point(lambda pixel: 0 if pixel < 165 else 255, mode="1")

    def extract_text_from_bytes(self, data: bytes) -> str:
        if not self.available():
            return ""
        with Image.open(io.BytesIO(data)) as image:
            prepared = self._prepare_image(image)
            return str(pytesseract.image_to_string(prepared) or "").strip()

    def extract_text_from_path(self, path: str) -> str:
        if not self.available():
            return ""
        with Image.open(path) as image:
            prepared = self._prepare_image(image)
            return str(pytesseract.image_to_string(prepared) or "").strip()

    def metadata(self) -> dict[str, Any]:
        return {
            "available": self.available(),
            "engine": "tesseract" if self.available() else "unavailable",
        }


ocr_service = OCRService()
