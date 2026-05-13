"""Chat API endpoints — the heart of the application."""
import json
import uuid
from typing import Annotated, AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ClearConversationRequest,
    ConversationMetadata,
)
from app.services.conversation import ConversationService
from app.services.llm import LLMError, LLMService, LLMTimeoutError

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["Chat"])

# ─── System prompt ────────────────────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """You are a helpful, knowledgeable AI assistant.

Guidelines:
- Be concise but complete in your answers
- If you don't know something, say so clearly
- Format code with appropriate markdown code blocks
- Be friendly and professional"""


# ─── Dependencies ─────────────────────────────────────────────────────────────
def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


async def get_redis(settings: Settings = Depends(get_settings)) -> AsyncGenerator:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def get_conversation_service(
    redis: aioredis.Redis = Depends(get_redis),
) -> ConversationService:
    return ConversationService(redis)


LLMDep = Annotated[LLMService, Depends(get_llm_service)]
ConvDep = Annotated[ConversationService, Depends(get_conversation_service)]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message and receive an AI response. Supports multi-turn conversations.",
)
async def chat(
    request: ChatRequest,
    llm: LLMDep,
    conv: ConvDep,
) -> ChatResponse:
    """
    Main chat endpoint.

    - Retrieves conversation history from Redis
    - Calls Ollama LLM with full context
    - Saves new messages to Redis
    - Returns response with token usage and latency
    """
    log = logger.bind(
        conversation_id=request.conversation_id,
        model=request.model,
        message_length=len(request.message),
    )
    log.info("chat_request_received")

    # 1. Get conversation history
    history = await conv.get_history(request.conversation_id)

    # 2. Build messages for LLM
    messages = history + [{"role": "user", "content": request.message}]

    # 3. Call LLM
    try:
        result = await llm.generate(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt or DEFAULT_SYSTEM_PROMPT,
        )
    except LLMTimeoutError:
        log.error("chat_timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM took too long to respond. Try a shorter message or smaller model.",
        )
    except LLMError as e:
        log.error("chat_llm_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {e}",
        )

    # 4. Save to history
    await conv.add_message(request.conversation_id, "user", request.message)
    await conv.add_message(request.conversation_id, "assistant", result["response"])

    log.info(
        "chat_response_sent",
        total_tokens=result["total_tokens"],
        latency_ms=result["latency_ms"],
    )

    return ChatResponse(
        response=result["response"],
        conversation_id=request.conversation_id,
        model=result["model"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        latency_ms=result["latency_ms"],
    )


@router.post(
    "/stream",
    summary="Stream a chat response",
    description="Stream tokens one by one — like ChatGPT typing effect.",
)
async def chat_stream(
    request: ChatRequest,
    llm: LLMDep,
    conv: ConvDep,
) -> StreamingResponse:
    """
    Streaming chat endpoint using Server-Sent Events (SSE).

    Client receives tokens as they arrive:
    data: {"token": "Hello", "done": false}
    data: {"token": " world", "done": false}
    data: {"token": "", "done": true, "conversation_id": "abc-123"}
    data: [DONE]
    """
    log = logger.bind(conversation_id=request.conversation_id)

    async def generate() -> AsyncGenerator[str, None]:
        history = await conv.get_history(request.conversation_id)
        messages = history + [{"role": "user", "content": request.message}]

        full_response = ""

        try:
            async for token in llm.stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                system_prompt=request.system_prompt or DEFAULT_SYSTEM_PROMPT,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"

            # Save to history after full response received
            await conv.add_message(request.conversation_id, "user", request.message)
            await conv.add_message(request.conversation_id, "assistant", full_response)

            # Send completion event
            yield f"data: {json.dumps({'token': '', 'done': True, 'conversation_id': request.conversation_id})}\n\n"
            yield "data: [DONE]\n\n"
            log.info("stream_complete", response_length=len(full_response))

        except LLMTimeoutError:
            yield f"data: {json.dumps({'error': 'timeout', 'message': 'LLM timed out'})}\n\n"
        except LLMError as e:
            yield f"data: {json.dumps({'error': 'llm_error', 'message': str(e)})}\n\n"
        except Exception as e:
            log.error("stream_error", error=str(e), exc_info=True)
            yield f"data: {json.dumps({'error': 'internal_error'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationMetadata,
    summary="Get conversation info",
)
async def get_conversation(
    conversation_id: str,
    conv: ConvDep,
) -> ConversationMetadata:
    """Get metadata about a conversation."""
    metadata = await conv.get_metadata(conversation_id)
    if not metadata["exists"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )
    return ConversationMetadata(**metadata)


@router.get(
    "/{conversation_id}/history",
    summary="Get conversation history",
)
async def get_conversation_history(
    conversation_id: str,
    conv: ConvDep,
    limit: int = 20,
) -> dict:
    """Get the full message history for a conversation."""
    messages = await conv.get_history(conversation_id, limit=limit)
    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "count": len(messages),
    }


@router.delete(
    "/{conversation_id}",
    summary="Clear conversation history",
)
async def clear_conversation(
    conversation_id: str,
    conv: ConvDep,
) -> dict:
    """Delete all messages in a conversation."""
    deleted = await conv.clear_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "cleared": deleted,
        "message": "Conversation cleared" if deleted else "Conversation not found",
    }
