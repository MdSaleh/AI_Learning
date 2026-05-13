"""Conversation service — manages multi-turn chat history in Redis."""
import json
from typing import Optional

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ConversationService:
    """Manages conversation history stored in Redis."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.ttl = settings.conversation_ttl_seconds
        self.max_messages = settings.max_history_messages

    def _key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}:messages"

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """Add a message to conversation history."""
        key = self._key(conversation_id)
        message = json.dumps({"role": role, "content": content})

        pipe = self.redis.pipeline()
        pipe.rpush(key, message)                     # Append to list
        pipe.ltrim(key, -self.max_messages, -1)      # Keep last N messages
        pipe.expire(key, self.ttl)                   # Refresh TTL
        await pipe.execute()

        logger.debug(
            "message_added",
            conversation_id=conversation_id,
            role=role,
            content_length=len(content),
        )

    async def get_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Retrieve conversation history."""
        key = self._key(conversation_id)
        limit = limit or self.max_messages

        raw_messages = await self.redis.lrange(key, -limit, -1)
        messages = [json.loads(m) for m in raw_messages]

        logger.debug(
            "history_retrieved",
            conversation_id=conversation_id,
            message_count=len(messages),
        )
        return messages

    async def clear_history(self, conversation_id: str) -> bool:
        """Delete all history for a conversation."""
        key = self._key(conversation_id)
        deleted = await self.redis.delete(key)
        logger.info("conversation_cleared", conversation_id=conversation_id)
        return bool(deleted)

    async def get_metadata(self, conversation_id: str) -> dict:
        """Get conversation stats."""
        key = self._key(conversation_id)
        message_count = await self.redis.llen(key)
        ttl = await self.redis.ttl(key)

        return {
            "conversation_id": conversation_id,
            "message_count": message_count,
            "ttl_seconds": ttl,
            "exists": message_count > 0,
        }
