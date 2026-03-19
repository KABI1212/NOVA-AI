import logging
import os
import warnings
from pathlib import Path

import aiofiles
import docx

from config.settings import settings

try:
    from cryptography.utils import CryptographyDeprecationWarning

    warnings.filterwarnings(
        "ignore",
        message=r".*ARC4 has been moved to cryptography\.hazmat\.decrepit\.ciphers\.algorithms\.ARC4.*",
        category=CryptographyDeprecationWarning,
        module=r"pypdf\._crypt_providers\._cryptography",
    )
except Exception:
    pass

from pypdf import PdfReader


logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file to disk."""
        file_path = self.upload_dir / filename

        async with aiofiles.open(file_path, "wb") as file_handle:
            await file_handle.write(file_content)

        return str(file_path)

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            reader = PdfReader(file_path)
            text = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text.append(page_text)
            return "\n".join(text).strip()
        except Exception as exc:
            logger.warning("PDF extraction failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error extracting PDF text: {exc}") from exc

    async def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as file_handle:
                return await file_handle.read()
        except Exception as exc:
            logger.warning("TXT extraction failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error reading TXT file: {exc}") from exc

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            document = docx.Document(file_path)
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            return "\n".join(paragraphs).strip()
        except Exception as exc:
            logger.warning("DOCX extraction failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error extracting DOCX text: {exc}") from exc

    async def process_document(self, file_path: str, file_type: str) -> str:
        """Process document and extract text based on file type."""
        if file_type == "pdf":
            return self.extract_text_from_pdf(file_path)
        if file_type == "txt":
            return await self.extract_text_from_txt(file_path)
        if file_type == "docx":
            return self.extract_text_from_docx(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from disk."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as exc:
            logger.warning("File deletion failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error deleting file: {exc}") from exc


document_service = DocumentService()
