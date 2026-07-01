from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models.user import User
from services.agent_controller import run_agent
from services.ai_orchestrator import run_orchestrator
from services.tool_registry import list_tools, run_tool
from utils.dependencies import get_current_user


router = APIRouter(prefix="/api/orchestrator", tags=["Orchestrator"])


class OrchestratorRequest(BaseModel):
    question: str


class ToolRunRequest(BaseModel):
    input: dict = Field(default_factory=dict)


@router.post("/compose")
async def compose_answer(
    request: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
):
    question = " ".join((request.question or "").split()).strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    _ = current_user
    return await run_orchestrator(question)


@router.post("/agent")
async def agent_answer(
    request: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
):
    question = " ".join((request.question or "").split()).strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    _ = current_user
    return await run_agent(question)


@router.get("/tools")
async def tools(current_user: User = Depends(get_current_user)):
    _ = current_user
    return {"tools": list_tools()}


@router.post("/tools/{tool_id}/run")
async def run_registered_tool(
    tool_id: str,
    request: ToolRunRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    try:
        return await run_tool(tool_id, request.input)
    except KeyError:
        raise HTTPException(status_code=404, detail="Tool not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
