from __future__ import annotations

from pathlib import Path
import zipfile

from services.document_service import document_service


def test_extract_text_from_xlsx_reads_shared_strings_and_values() -> None:
    artifact_dir = Path(__file__).resolve().parent / ".artifacts"
    artifact_dir.mkdir(exist_ok=True)
    workbook_path = artifact_dir / "sample.xlsx"

    if workbook_path.exists():
        workbook_path.unlink()

    try:
        with zipfile.ZipFile(workbook_path, "w") as archive:
            archive.writestr(
                "xl/sharedStrings.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2">
  <si><t>Name</t></si>
  <si><t>Value</t></si>
</sst>""",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>Score</t></is></c>
      <c r="B2"><v>42</v></c>
    </row>
  </sheetData>
</worksheet>""",
            )

        extracted = document_service.extract_text_from_xlsx(str(workbook_path))

        assert "Sheet1" in extracted
        assert "Name | Value" in extracted
        assert "Score | 42" in extracted
    finally:
        if workbook_path.exists():
            workbook_path.unlink()
