from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from services.search_service import search_web, fetch_page_content, format_results_for_ai
from services.ai_service import stream_chat
from utils.dependencies import get_current_user
import json

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query:       str
    model:       str  = "gpt-4"
    deep:        bool = False   # fetch full page content?
    max_results: int  = 5

class SearchChatRequest(BaseModel):
    message:     str
    model:       Optional[str] = None
    provider:    Optional[str] = None
    history:     list = []

# ── Raw search endpoint ───────────────────────────────────
@router.post("/query")
async def search_query(
    request: SearchRequest,
    user=Depends(get_current_user)
):
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        results = await search_web(request.query, request.max_results)

        # Optionally fetch full content for top result
        if request.deep and results and results[0].get("url"):
            top_url      = results[0]["url"]
            full_content = await fetch_page_content(top_url)
            results[0]["full_content"] = full_content

        return {"results": results, "query": request.query}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI-powered search chat (streams answer) ───────────────
@router.post("/chat")
async def search_chat(
    request: SearchChatRequest,
    user=Depends(get_current_user)
):
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        # Step 1: Search web
        results = await search_web(request.message, max_results=5)

        # Step 2: Build AI prompt with search context
        search_context = format_results_for_ai(results)
        today = datetime.utcnow().strftime("%B %d, %Y")

        system_prompt = (
            "You are NOVA-AI with web search capabilities.\n"
            f"Today's date is {today}.\n"
            "You have access to real-time web search results below.\n\n"
            "Instructions:\n"
            "- Answer using the search results as your primary source\n"
            "- Always cite sources using [1], [2] etc. matching the result numbers\n"
            "- If search results don't contain the answer, say so honestly\n"
            "- If the user asks about a specific year or range such as 2024 to 2025, prioritize results that match those years exactly\n"
            "- Be concise and accurate\n"
            "- Include the source URLs at the end of your response\n\n"
            + search_context
        )

        messages = [
            *request.history,
            {"role": "user", "content": request.message}
        ]

        # Step 3: Stream AI response with search context injected
        async def event_generator():
            try:
                # First emit the search results metadata
                meta = json.dumps({
                    "type":    "search_results",
                    "results": results,
                    "query":   request.message,
                })
                yield f"data: {meta}\n\n"          # ← fixed: proper \n\n

                # Then stream the AI answer
                async for chunk in stream_chat(
                    [{"role": "system", "content": system_prompt}, *messages],
                    model=request.model,
                    provider=request.provider
                ):
                    data = json.dumps({"type": "chunk", "content": chunk})
                    yield f"data: {data}\n\n"       # ← fixed: proper \n\n

            except Exception as e:
                error = json.dumps({"type": "error", "content": str(e)})
                yield f"data: {error}\n\n"

            finally:
                yield "data: [DONE]\n\n"            # ← fixed: proper \n\n

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":     "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
