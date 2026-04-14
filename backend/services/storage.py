from __future__ import annotations

import asyncio
import mimetypes
import os
import re
import shlex
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles

from config.settings import settings


def sanitize_filename(filename: str) -> str:
    source = Path(filename or "file")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "file"
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", source.suffix or "").lower()
    return f"{stem}{suffix}"


class StorageService:
    def __init__(self) -> None:
        self.base_dir = Path(settings.UPLOAD_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def resolve_user_dir(self, user_id: int | str | None) -> Path:
        safe_user = re.sub(r"[^A-Za-z0-9_-]+", "_", str(user_id or "anonymous")).strip("_") or "anonymous"
        target = (self.base_dir / "files" / safe_user).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    async def save_upload(self, *, user_id: int | str | None, original_name: str, content: bytes) -> dict[str, Any]:
        safe_name = sanitize_filename(original_name)
        suffix = Path(safe_name).suffix.lower()
        stored_name = f"{Path(safe_name).stem}_{uuid4().hex[:12]}{suffix}"
        target_dir = self.resolve_user_dir(user_id)
        target_path = target_dir / stored_name

        async with aiofiles.open(target_path, "wb") as file_handle:
            await file_handle.write(content)

        mime_type, _ = mimetypes.guess_type(safe_name)
        return {
            "filename": stored_name,
            "original_name": safe_name,
            "mime_type": mime_type or "application/octet-stream",
            "storage_path": str(target_path),
            "extension": suffix,
        }

    async def read_bytes(self, path: str) -> bytes:
        async with aiofiles.open(path, "rb") as file_handle:
            return await file_handle.read()

    def delete_file(self, path: str) -> None:
        candidate = Path(path or "").resolve()
        if not str(candidate).startswith(str(self.base_dir)):
            return
        if candidate.exists():
            candidate.unlink(missing_ok=True)

    async def run_malware_scan(self, path: str) -> dict[str, Any]:
        command_template = str(settings.MALWARE_SCAN_COMMAND or "").strip()
        if not command_template:
            return {
                "status": "skipped",
                "reason": "scanner_not_configured",
            }

        quoted_path = shlex.quote(path)
        command = command_template.replace("{path}", quoted_path)
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=max(1, int(settings.MALWARE_SCAN_TIMEOUT_SECONDS)),
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {
                "status": "timeout",
                "reason": "scan_timed_out",
            }

        return {
            "status": "clean" if process.returncode == 0 else "flagged",
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="ignore").strip(),
            "stderr": stderr.decode("utf-8", errors="ignore").strip(),
        }


storage_service = StorageService()
