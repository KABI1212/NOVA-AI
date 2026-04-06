import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.ai_service import stream_chat
from services.search_service import fetch_page_content, format_results_for_ai, search_web
from utils.dependencies import get_current_user

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    model: str = "gpt-4"
    deep: bool = False
    max_results: int = 5


class SearchChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None
    history: list = []


@router.post("/query")
async def search_query(
    request: SearchRequest,
    user=Depends(get_current_user),
):
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        results = await search_web(request.query, request.max_results)

        if request.deep and results and results[0].get("url"):
            top_url = results[0]["url"]
            results[0]["full_content"] = await fetch_page_content(top_url)

        return {"results": results, "query": request.query}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat")
async def search_chat(
    request: SearchChatRequest,
    user=Depends(get_current_user),
):
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        results = await search_web(request.message, max_results=5)
        search_context = format_results_for_ai(results)
        today = datetime.utcnow().strftime("%B %d, %Y")

        system_prompt = (
            "You are NOVA-AI with web search capabilities.\n"
            f"Today's date is {today}.\n"
            "You have access to real-time web search results below.\n\n"
            "Instructions:\n"
            "- Answer using the search results as your primary source\n"
            "- Always cite sources using [1], [2] etc. matching the result numbers\n"
            "- If search results don't contain the answer, say \"I don't know based on the search results\"\n"
            "- If the user asks about a specific year or range such as 2024 to 2025, prioritize results that match those years exactly\n"
            "- Do not guess, invent facts, or imply certainty when the evidence is weak\n"
            "- Be concise and accurate\n"
            "- Include the source URLs at the end of your response\n\n"
            + search_context
        )

        messages = [*request.history, {"role": "user", "content": request.message}]

        async def event_generator():
            full_response = ""
            try:
                meta = json.dumps(
                    {
                        "type": "search_results",
                        "results": results,
                        "query": request.message,
                    }
                )
                yield f"data: {meta}\n\n"

                async for chunk in stream_chat(
                    [{"role": "system", "content": system_prompt}, *messages],
                    model=request.model,
                    provider=request.provider,
                    use_case="research",
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

                full_response = full_response.strip()
                if not full_response:
                    raise RuntimeError("Search chat returned an empty response")
                yield f"data: {json.dumps({'type': 'final', 'message': full_response, 'results': results})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
