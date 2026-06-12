import time
import aiosqlite
from loguru import logger


class MemoryDB:

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        conn.row_factory = aiosqlite.Row

    async def commit(self):
        await self._conn.commit()

    async def insert_episodic_memory(self, summary: str, importance: float = 0.5,
                                      emotion_label: str = "", session_id: str = "user",
                                      embedding_id: int = -1, auto_commit: bool = True):
        cursor = await self._conn.execute(
            """INSERT INTO episodic_memories
               (timestamp, summary, importance, emotion_label, session_id, embedding_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (time.time(), summary, importance, emotion_label, session_id, embedding_id),
        )
        if auto_commit:
            await self._conn.commit()
        return cursor.lastrowid

    async def get_memory_by_id(self, memory_id: int) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM episodic_memories WHERE id=?", (memory_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_recent_conversations(self, limit: int = 20):
        cursor = await self._conn.execute(
            """SELECT * FROM conversation_logs
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def search_memories_by_importance(self, min_importance: float = 0.3, limit: int = 10):
        cursor = await self._conn.execute(
            """SELECT * FROM episodic_memories
               WHERE importance >= ?
               ORDER BY timestamp DESC LIMIT ?""",
            (min_importance, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_memories(self):
        cursor = await self._conn.execute(
            "SELECT * FROM episodic_memories ORDER BY timestamp DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_memory(self, memory_id: int, auto_commit: bool = True):
        await self._conn.execute("DELETE FROM episodic_memories WHERE id=?", (memory_id,))
        if auto_commit:
            await self._conn.commit()

    async def delete_memory_with_vector(self, memory_id: int, vector_store=None, auto_commit: bool = True):
        """统一删除：先删向量，再删记忆"""
        if vector_store:
            try:
                await vector_store.delete(memory_id)
            except Exception as e:
                logger.warning("db_memory.vec_delete_failed", memory_id=memory_id, error=str(e))
        await self.delete_memory(memory_id, auto_commit=auto_commit)

    async def get_episodic_recent(self, limit: int = 50):
        cursor = await self._conn.execute(
            """SELECT * FROM episodic_memories
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_episodic_count(self) -> int:
        cursor = await self._conn.execute("SELECT COUNT(*) as cnt FROM episodic_memories")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def insert_portrait(self, content: str, version: int = 1,
                               source_ids: str = "", change_log: str = "",
                               auto_commit: bool = True) -> int:
        cursor = await self._conn.execute(
            """INSERT INTO user_portrait (content, version, source_ids, change_log, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (content, version, source_ids, change_log, time.time()),
        )
        if auto_commit:
            await self._conn.commit()
        return cursor.lastrowid

    async def get_latest_portrait(self) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM user_portrait ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
