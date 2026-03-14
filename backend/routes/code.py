from fastapi import APIRouter, Depends
from pydantic import BaseModel
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user

router = APIRouter(prefix="/api/code", tags=["Code Assistant"])


class CodeGenerateRequest(BaseModel):
    prompt: str
    language: str = "python"


class CodeExplainRequest(BaseModel):
    code: str
    language: str = "python"


class CodeDebugRequest(BaseModel):
    code: str
    error: str = ""


class CodeOptimizeRequest(BaseModel):
    code: str
    language: str = "python"


@router.post("/generate")
async def generate_code(
    request: CodeGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate code based on prompt"""
    code = await ai_service.generate_code(request.prompt, request.language)

    return {
        "language": request.language,
        "code": code
    }


@router.post("/explain")
async def explain_code(
    request: CodeExplainRequest,
    current_user: User = Depends(get_current_user)
):
    """Explain code step-by-step"""
    explanation = await ai_service.explain_code(request.code, request.language)

    return {
        "explanation": explanation
    }


@router.post("/debug")
async def debug_code(
    request: CodeDebugRequest,
    current_user: User = Depends(get_current_user)
):
    """Debug code and suggest fixes"""
    debug_result = await ai_service.debug_code(request.code, request.error)

    return {
        "debug_result": debug_result
    }


@router.post("/optimize")
async def optimize_code(
    request: CodeOptimizeRequest,
    current_user: User = Depends(get_current_user)
):
    """Optimize code and suggest improvements"""
    optimization = await ai_service.optimize_code(request.code, request.language)

    return {
        "optimization": optimization
    }
