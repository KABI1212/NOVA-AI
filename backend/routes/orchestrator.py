from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from models.user import User
from services.agent_controller import run_agent
from services.ai_orchestrator import run_orchestrator
from utils.dependencies import get_current_user


router = APIRouter(prefix="/api/orchestrator", tags=["Orchestrator"])


class OrchestratorRequest(BaseModel):
    question: str


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
