import asyncio
import time
from loguru import logger

from database import DatabaseManager
from db_memory import MemoryDB
from vector_store import VectorStore
from atomic_write import atomic_json_write


def _extract_entities(text: str) -> list[str]:
    try:
        import jieba
        words = jieba.cut(text)
        return [w for w in words if len(w) >= 2]
    except ImportError:
        return [text[i:i+n] for n in range(2, 5) for i in range(len(text)-n+1)]


class MemoryManager:

    IDLE_THRESHOLD = 30
    ENCODE_COOLDOWN = 60

    def __init__(self, db: DatabaseManager, memory: MemoryDB,
                 vector_store: VectorStore | None = None,
                 router=None, knowledge_graph=None, security_filter=None):
        self.db = db
        self.memory = memory
        self.vec = vector_store
        self.router = router
        self.kg = knowledge_graph
        self._security_filter = security_filter
        self._last_message_time: float = 0
        self._last_encode_time: float = 0
        self._pending_encode = False

    def set_knowledge_graph(self, kg):
        self.kg = kg

    def signal_new_message(self):
        self._last_message_time = time.time()
        self._pending_encode = True

    async def retrieve_memories(self, query: str, k: int = 5) -> list[dict]:
        results = []

        if self.vec:
            try:
                vec_results = await self.vec.search(query, top_k=k)
                if vec_results:
                    for row_id, distance in vec_results:
                        mem = await self.memory.get_memory_by_id(row_id)
                        if mem:
                            mem["score"] = 1.0 - distance
                            results.append(mem)
            except Exception as e:
                logger.warning("memory.vec_search_failed", error=str(e))

        if not results and self.memory:
            try:
                results = await self.memory.search_memories_by_importance(
                    min_importance=0.4, limit=k
                )
            except Exception as e:
                logger.warning("memory.fallback_search_failed", error=str(e))

        now = time.time()
        for r in results:
            age_hours = (now - r.get("timestamp", 0)) / 3600
            importance = r.get("importance", 0.5)
            r["effective_score"] = importance * max(0.1, 1.0 - age_hours / 168)

        results.sort(key=lambda x: x.get("effective_score", 0), reverse=True)
        results = results[:k]

        if self.kg and results:
            try:
                entity_names = []
                for r in results[:2]:
                    summary = r.get("summary", "")
                    candidates = _extract_entities(summary)
                    for word in candidates:
                        if word not in ("用户", "助手", "人家"):
                            entity_names.append(word)
                entity_names = list(set(entity_names))[:3]
                if entity_names:
                    knowledge = await self.kg.get_related_knowledge(entity_names)
                    if knowledge:
                        kg_context = await self.kg.format_knowledge_context(knowledge)
                        if kg_context and results:
                            results[0]["kg_context"] = kg_context
            except Exception as e:
                logger.debug("memory.kg_expand_failed", error=str(e))

        return results

    async def encode_memory(self, context: dict):
        exchanges = context.get("exchanges", [])
        if not exchanges or len(exchanges) < 2:
            return

        summary = self._generate_summary(exchanges)

        # 记忆写入安全扫描
        from security import SecurityFilter
        security = self._security_filter or SecurityFilter()
        threat_result = security.scan_threats(summary, scope="strict")
        if not threat_result.is_safe and threat_result.action == "block":
            logger.warning("memory.security_blocked", threat=threat_result.threat_type)
            return  # 阻止保存可疑记忆

        importance = self._estimate_importance(exchanges, context)
        emotion = context.get("emotion", {}).get("primary", "")

        try:
            mem_id = await self.memory.insert_episodic_memory(
                summary=summary,
                importance=importance,
                emotion_label=emotion,
            )

            if self.vec and summary:
                await self.vec.upsert(mem_id, summary)

            self._last_encode_time = time.time()
            self._pending_encode = False
            logger.info("memory.encoded", summary=summary[:80], importance=importance)

            # 原子写入记忆状态到 JSON 文件
            self._save_state_json(summary, importance, emotion)
        except Exception as e:
            logger.warning("memory.encode_failed", error=str(e))

        if self.kg and summary:
            try:
                await self.kg.auto_extract_and_merge(summary)
            except Exception as e:
                logger.debug("memory.kg_extract_failed", error=str(e))

    def _generate_summary(self, exchanges: list[dict]) -> str:
        parts = []
        for msg in exchanges[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content:
                parts.append(f"用户: {content[:100]}")
            elif role == "assistant" and content:
                parts.append(f"助手: {content[:100]}")

        summary = " | ".join(parts)
        return summary[:500]

    def _estimate_importance(self, exchanges: list[dict], context: dict) -> float:
        importance = 0.3

        emotion = context.get("emotion", {})
        if emotion.get("primary") in ("悲伤", "愤怒", "焦虑", "恐惧"):
            importance += 0.3
        elif emotion.get("primary") in ("喜悦", "感激", "期待"):
            importance += 0.1

        total_len = sum(len(m.get("content", "")) for m in exchanges)
        if total_len > 500:
            importance += 0.2

        return min(importance, 1.0)

    async def try_idle_encode(self, context: dict, force: bool = False):
        now = time.time()
        if not self._pending_encode:
            return
        if not force and now - self._last_message_time < self.IDLE_THRESHOLD:
            return
        if now - self._last_encode_time < self.ENCODE_COOLDOWN:
            return

        await self.encode_memory(context)

    def _save_state_json(self, summary: str, importance: float, emotion: str):
        """原子写入记忆状态到 JSON 文件"""
        try:
            from pathlib import Path
            state_dir = Path(__file__).parent / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_path = str(state_dir / "memory_state.json")
            data = {
                "last_summary": summary[:500],
                "last_importance": importance,
                "last_emotion": emotion,
                "last_encode_time": self._last_encode_time,
            }
            atomic_json_write(state_path, data)
        except Exception as e:
            logger.warning("memory.state_json_save_failed", error=str(e))

    async def shutdown(self) -> str:
        if self.vec:
            await self.vec.close()
        return "done"
