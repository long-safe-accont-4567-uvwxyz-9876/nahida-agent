import json
import time
from loguru import logger
from db_learning import LearningDB


class LearningManager:

    def __init__(self, db=None, learning_db: LearningDB | None = None, router=None):
        self._db = db
        self.learning_db = learning_db
        self._router = router

    def set_db(self, db):
        self._db = db

    def set_learning_db(self, learning_db: LearningDB):
        self.learning_db = learning_db

    def set_router(self, router):
        self._router = router

    async def record_interaction(self, user_input: str, assistant_reply: str,
                                  user_id: str = "", context: dict | None = None):
        if not self.learning_db:
            return

        try:
            interaction_data = {
                "user_input": user_input[:500],
                "assistant_reply": assistant_reply[:500],
                "user_id": user_id,
                "timestamp": time.time(),
                "context": context or {},
            }
            await self.learning_db.insert_learning_record(
                category="interaction",
                content=json.dumps(interaction_data, ensure_ascii=False),
                importance=1,
            )
        except Exception as e:
            logger.debug("learning.record_failed", error=str(e))

    async def get_learning_context(self, query: str = "", limit: int = 3) -> str:
        if not self.learning_db:
            return ""

        try:
            records = await self.learning_db.search_learning_records(query, limit=limit)
            if not records:
                return ""

            parts = ["[学习经验]"]
            for r in records:
                parts.append(f"- {r.get('content', '')[:200]}")
            return "\n".join(parts)
        except Exception as e:
            logger.debug("learning.context_failed", error=str(e))
            return ""

    async def get_stats(self) -> dict:
        if not self.learning_db:
            return {}

        try:
            return await self.learning_db.get_stats()
        except Exception:
            return {}
