"""LLM chat endpoints. Phase-1 stub; populated in Phase 5."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings

router = APIRouter()


@router.get("/info")
def chat_info() -> dict:
    """Report chat-service availability without revealing the API key."""
    return {
        "model": settings.llm_model,
        "available": bool(settings.anthropic_api_key),
        "max_tokens": settings.llm_max_tokens,
    }
