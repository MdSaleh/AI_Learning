"""Request and response models for the Chat API."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Request Models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body for a chat message."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="The user's message",
        examples=["What is machine learning?"],
    )
    conversation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Conversation ID for multi-turn chat. Auto-generated if not provided.",
    )
    model: str = Field(
        default="llama3.1:8b",
        description="LLM model to use",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Higher = more creative.",
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Maximum tokens in response",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Custom system prompt to override default",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )

    @field_validator("message")
    @classmethod
    def strip_and_validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty or whitespace only")
        return v


class ClearConversationRequest(BaseModel):
    """Request to clear conversation history."""
    conversation_id: str


# ─── Response Models ──────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """Response from a chat request."""

    response: str = Field(description="The AI's response")
    conversation_id: str = Field(description="Conversation ID for follow-up messages")
    model: str = Field(description="Model used to generate the response")
    prompt_tokens: int = Field(description="Tokens in the prompt")
    completion_tokens: int = Field(description="Tokens in the completion")
    total_tokens: int = Field(description="Total tokens used")
    latency_ms: float = Field(description="Response time in milliseconds")


class ConversationMetadata(BaseModel):
    """Metadata about a conversation."""
    conversation_id: str
    message_count: int
    ttl_seconds: int
    exists: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    ollama_connected: bool
    redis_connected: bool


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    request_id: Optional[str] = None
