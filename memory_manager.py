import json
import time
from pathlib import Path
from loguru import logger

from db_memory import MemoryDB


class MemoryManager:

    def __init__(self, memory_db: MemoryDB | None = None, vector_store=None, router=None):
        self.memory_db = memory_db
        self.vector_store = vector_store
        self._router = router

    def set_memory_db(self, memory_db: MemoryDB):
        self.memory_db = memory_db

    def set_vector_store(self, vector_store):
        self.vector_store = vector_store

    def set_router(self, router):
        self._router = router

    async def remember(self, content: str, tags: list[str] | None = None,
                        source: str = "conversation",
                        importance: int = 3,
                        user_id: str = "") -> bool:
        if not self.memory_db:
            return False

        try:
            memory_id = await self.memory_db.insert_episodic_memory(
                content=content,
                tags=tags or [],
                source=source,
                importance=importance,
                user_id=user_id,
            )

            if memory_id and self.vector_store:
                await self.vector_store.upsert(memory_id, content)

            return bool(memory_id)
        except Exception as e:
            logger.warning("memory.remember_failed", error=str(e))
            return False

    async def recall(self, query: str, limit: int = 5) -> list[dict]:
        if not self.memory_db:
            return []

        try:
            if self.vector_store:
                vec_results = await self.vector_store.search(query, top_k=limit)
                if vec_results:
                    ids = [r[0] for r in vec_results]
                    memories = await self.memory_db.get_memories_by_ids(ids)
                    if memories:
                        return memories

            return await self.memory_db.search_memories(query, limit=limit)
        except Exception as e:
            logger.warning("memory.recall_failed", error=str(e))
            return []

    async def forget(self, query: str, user_id: str = "") -> int:
        if not self.memory_db:
            return 0

        try:
            return await self.memory_db.delete_memories_by_query(query, user_id=user_id)
        except Exception as e:
            logger.warning("memory.forget_failed", error=str(e))
            return 0

    async def get_context_string(self, query: str, limit: int = 3) -> str:
        memories = await self.recall(query, limit=limit)
        if not memories:
            return ""

        parts = ["[相关记忆]"]
        for m in memories:
            content = m.get("content", "")[:200]
            tags = m.get("tags", [])
            tag_str = " ".join(f"#{t}" for t in tags[:3]) if tags else ""
            parts.append(f"- {content} {tag_str}")
        return "\n".join(parts)

    async def get_stats(self) -> dict:
        if not self.memory_db:
            return {}

        try:
            return await self.memory_db.get_stats()
        except Exception:
            return {}
