"""LLM chat endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.llm_service import LLMService

router = APIRouter()


@router.get("/info")
def chat_info() -> dict:
    """Report chat-service availability without revealing the API key."""
    return {
        "model": settings.llm_model,
        "available": bool(settings.anthropic_api_key),
        "max_tokens": settings.llm_max_tokens,
    }


@router.post("/message", response_model=ChatResponse)
def chat_message(req: ChatRequest) -> ChatResponse:
    """One round-trip through Claude + the op3 sandbox."""
    svc = LLMService()
    if not svc.available:
        raise HTTPException(
            status_code=503,
            detail=("Chat service unavailable: ANTHROPIC_API_KEY not set. "
                    "See op3_studio/.env.example for setup."),
        )
    try:
        result = svc.chat(
            message=req.message,
            history=[m.model_dump() for m in req.conversation_history],
            project_state=req.project_state,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(
        reply=result.reply,
        code_executed=result.code_executed or None,
        results=[r.__dict__ for r in result.results] or None,
        error=result.error,
    )
