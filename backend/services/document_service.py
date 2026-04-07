import logging
import os
import re
import warnings
from pathlib import Path
from xml.etree import ElementTree as ET
from uuid import uuid4
import zipfile

import aiofiles
import docx
from bs4 import BeautifulSoup

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
    TEXT_LIKE_TYPES = {
        "txt",
        "md",
        "csv",
        "json",
        "py",
        "js",
        "jsx",
        "ts",
        "tsx",
        "html",
        "htm",
        "css",
        "xml",
        "yml",
        "yaml",
    }
    SPREADSHEET_TYPES = {
        "xlsx",
        "xlsm",
    }

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file to disk."""
        original_path = Path(filename or "document")
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", original_path.stem).strip("._") or "document"
        safe_suffix = original_path.suffix or ""
        stored_name = f"{safe_stem}_{uuid4().hex[:12]}{safe_suffix}"
        file_path = self.upload_dir / stored_name

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
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
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

    def extract_text_from_xlsx(self, file_path: str) -> str:
        """Extract readable text from XLSX/XLSM spreadsheets."""
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        def _shared_string_text(node: ET.Element) -> str:
            parts = [
                "".join(text for text in fragment.itertext())
                for fragment in node.findall(".//main:t", namespace)
            ]
            return "".join(parts).strip()

        try:
            with zipfile.ZipFile(file_path) as workbook:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in workbook.namelist():
                    shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                    shared_strings = [
                        _shared_string_text(item)
                        for item in shared_root.findall("main:si", namespace)
                    ]

                worksheet_names = sorted(
                    name
                    for name in workbook.namelist()
                    if name.startswith("xl/worksheets/") and name.endswith(".xml")
                )
                sheet_sections: list[str] = []

                for worksheet_name in worksheet_names:
                    root = ET.fromstring(workbook.read(worksheet_name))
                    row_lines: list[str] = []

                    for row in root.findall(".//main:sheetData/main:row", namespace):
                        cell_values: list[str] = []

                        for cell in row.findall("main:c", namespace):
                            cell_type = cell.attrib.get("t", "")
                            value_node = cell.find("main:v", namespace)
                            inline_node = cell.find("main:is", namespace)

                            if cell_type == "inlineStr" and inline_node is not None:
                                value = "".join(inline_node.itertext()).strip()
                            elif value_node is None or value_node.text is None:
                                value = ""
                            else:
                                raw_value = value_node.text.strip()
                                if cell_type == "s":
                                    try:
                                        value = shared_strings[int(raw_value)]
                                    except (ValueError, IndexError):
                                        value = raw_value
                                elif cell_type == "b":
                                    value = "TRUE" if raw_value == "1" else "FALSE"
                                else:
                                    value = raw_value

                            if value:
                                cell_values.append(value)

                        if cell_values:
                            row_lines.append(" | ".join(cell_values))

                    if row_lines:
                        sheet_label = Path(worksheet_name).stem.replace("_", " ").title()
                        sheet_sections.append(
                            f"{sheet_label}\n" + "\n".join(row_lines)
                        )

                return "\n\n".join(sheet_sections).strip()
        except Exception as exc:
            logger.warning("XLSX extraction failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error extracting XLSX text: {exc}") from exc

    async def extract_text_from_text_like(self, file_path: str, file_type: str) -> str:
        """Extract text from plain-text-like and source-code files."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                raw_text = await file_handle.read()
        except Exception as exc:
            logger.warning("Text-like extraction failed file=%s error=%s", file_path, exc)
            raise RuntimeError(f"Error reading {file_type.upper()} file: {exc}") from exc

        if file_type in {"html", "htm"}:
            return BeautifulSoup(raw_text, "html.parser").get_text("\n").strip()

        return raw_text.strip()

    async def process_document(self, file_path: str, file_type: str) -> str:
        """Process document and extract text based on file type."""
        if file_type == "pdf":
            return self.extract_text_from_pdf(file_path)
        if file_type == "txt":
            return await self.extract_text_from_txt(file_path)
        if file_type == "docx":
            return self.extract_text_from_docx(file_path)
        if file_type in self.SPREADSHEET_TYPES:
            return self.extract_text_from_xlsx(file_path)
        if file_type in self.TEXT_LIKE_TYPES:
            return await self.extract_text_from_text_like(file_path, file_type)
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
