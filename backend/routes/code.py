import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user

router = APIRouter(prefix="/api/code", tags=["Code Assistant"])


class CodeGenerateRequest(BaseModel):
    prompt: str
    language: str = "python"
    sample_input: str = ""


class CodeExplainRequest(BaseModel):
    code: str
    language: str = "python"
    sample_input: str = ""


class CodeDebugRequest(BaseModel):
    code: str
    language: str = "python"
    error: str = ""
    sample_input: str = ""


class CodeOptimizeRequest(BaseModel):
    code: str
    language: str = "python"
    sample_input: str = ""


def _extract_markdown_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ims)^\s*##\s*{re.escape(heading)}\s*$\s*(?P<body>.*?)(?=^\s*##\s+|\Z)"
    )
    match = pattern.search(str(text or ""))
    return match.group("body").strip() if match else ""


def _strip_wrapping_code_fence(text: str) -> str:
    cleaned = str(text or "").strip()
    fenced_match = re.match(r"^\s*```[^\n]*\n(?P<body>.*?)\n```\s*$", cleaned, re.S)
    if fenced_match:
        return fenced_match.group("body").strip()
    return cleaned


def _extract_first_code_block(text: str) -> str:
    match = re.search(r"```[^\n]*\n(?P<body>.*?)\n```", str(text or ""), re.S)
    return match.group("body").strip() if match else ""


@router.post("/generate")
async def generate_code(
    request: CodeGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate code based on prompt"""
    response_markdown = await ai_service.generate_code(
        request.prompt,
        request.language,
        request.sample_input,
    )
    summary = _extract_markdown_section(response_markdown, "Summary")
    notes = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Notes"))
    output = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Output"))
    code = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Code")) or _extract_first_code_block(response_markdown)

    return {
        "language": request.language,
        "code": code or response_markdown,
        "summary": summary,
        "output": output,
        "notes": notes,
        "response_markdown": response_markdown,
    }


@router.post("/explain")
async def explain_code(
    request: CodeExplainRequest,
    current_user: User = Depends(get_current_user)
):
    """Explain code step-by-step"""
    response_markdown = await ai_service.explain_code(
        request.code,
        request.language,
        request.sample_input,
    )
    summary = _extract_markdown_section(response_markdown, "Summary")
    explanation = _extract_markdown_section(response_markdown, "Explanation") or summary or response_markdown
    key_points = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Key points"))
    output = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Output"))

    return {
        "language": request.language,
        "summary": summary,
        "explanation": explanation,
        "output": output,
        "key_points": key_points,
        "response_markdown": response_markdown,
    }


@router.post("/debug")
async def debug_code(
    request: CodeDebugRequest,
    current_user: User = Depends(get_current_user)
):
    """Debug code and suggest fixes"""
    response_markdown = await ai_service.debug_code(
        request.code,
        request.language,
        request.error,
        request.sample_input,
    )
    root_cause = _extract_markdown_section(response_markdown, "Root cause")
    fixed_code = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Fixed code")) or _extract_first_code_block(response_markdown)
    output = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Output"))
    fix_notes = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Fix notes"))

    return {
        "language": request.language,
        "debug_result": root_cause or response_markdown,
        "root_cause": root_cause,
        "fixed_code": fixed_code,
        "output": output,
        "fix_notes": fix_notes,
        "response_markdown": response_markdown,
    }


@router.post("/optimize")
async def optimize_code(
    request: CodeOptimizeRequest,
    current_user: User = Depends(get_current_user)
):
    """Optimize code and suggest improvements"""
    response_markdown = await ai_service.optimize_code(
        request.code,
        request.language,
        request.sample_input,
    )
    summary = _extract_markdown_section(response_markdown, "Summary")
    optimized_code = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Improved code")) or _extract_first_code_block(response_markdown)
    output = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Output"))
    improvements = _strip_wrapping_code_fence(_extract_markdown_section(response_markdown, "Improvements"))

    return {
        "language": request.language,
        "optimization": summary or response_markdown,
        "summary": summary,
        "optimized_code": optimized_code,
        "output": output,
        "improvements": improvements,
        "response_markdown": response_markdown,
    }
