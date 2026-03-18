import os
from typing import Optional
from pypdf import PdfReader
import docx
import aiofiles
from pathlib import Path
from config.settings import settings


class DocumentService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file to disk"""
        file_path = self.upload_dir / filename

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)

        return str(file_path)

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            reader = PdfReader(file_path)
            text = ""

            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting PDF text: {str(e)}")

    async def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                text = await f.read()
            return text
        except Exception as e:
            raise Exception(f"Error reading TXT file: {str(e)}")

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            document = docx.Document(file_path)
            paragraphs = [para.text for para in document.paragraphs]
            return "\n".join(paragraphs).strip()
        except Exception as e:
            raise Exception(f"Error extracting DOCX text: {str(e)}")

    async def process_document(self, file_path: str, file_type: str) -> str:
        """Process document and extract text based on file type"""
        if file_type == "pdf":
            return self.extract_text_from_pdf(file_path)
        elif file_type == "txt":
            return await self.extract_text_from_txt(file_path)
        elif file_type == "docx":
            return self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from disk"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            raise Exception(f"Error deleting file: {str(e)}")


# Singleton instance
document_service = DocumentService()
