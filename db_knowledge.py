import time
import json
import aiosqlite
from loguru import logger


class KnowledgeDB:

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        conn.row_factory = aiosqlite.Row

    async def insert_knowledge_entity(self, entity_id: str, name: str,
                                       kind: str = "", observations: list | None = None):
        obs_json = json.dumps(observations or [], ensure_ascii=False)
        await self._conn.execute(
            """INSERT OR IGNORE INTO knowledge_entities (id, name, kind, observations, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (entity_id, name, kind, obs_json, time.time()),
        )
        await self._conn.commit()

    async def get_knowledge_entity(self, name: str) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM knowledge_entities WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_knowledge_entity(self, name: str, kind: str = "",
                                       observations: list | None = None):
        obs_json = json.dumps(observations or [], ensure_ascii=False)
        now = time.time()
        existing = await self.get_knowledge_entity(name)
        if existing:
            await self._conn.execute(
                """UPDATE knowledge_entities SET kind=?, observations=?, updated_at=?
                   WHERE name=?""",
                (kind, obs_json, now, name),
            )
        else:
            entity_id = f"ENT-{int(now % 100000):05d}"
            await self._conn.execute(
                """INSERT INTO knowledge_entities (id, name, kind, observations, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (entity_id, name, kind, obs_json, now),
            )
        await self._conn.commit()

    async def insert_knowledge_relation(self, relation_id: str, from_entity: str,
                                         relation_type: str, to_entity: str):
        await self._conn.execute(
            """INSERT OR IGNORE INTO knowledge_relations (id, from_entity, relation_type, to_entity, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (relation_id, from_entity, relation_type, to_entity, time.time()),
        )
        await self._conn.commit()

    async def get_knowledge_relations(self, entity_name: str, direction: str = "both") -> list[dict]:
        if direction == "outgoing":
            cursor = await self._conn.execute(
                "SELECT * FROM knowledge_relations WHERE from_entity=?", (entity_name,)
            )
        elif direction == "incoming":
            cursor = await self._conn.execute(
                "SELECT * FROM knowledge_relations WHERE to_entity=?", (entity_name,)
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM knowledge_relations WHERE from_entity=? OR to_entity=?",
                (entity_name, entity_name),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def search_knowledge_entities(self, query: str, limit: int = 10) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM knowledge_entities WHERE name LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_knowledge_entity(self, name: str) -> bool:
        cursor = await self._conn.execute(
            "DELETE FROM knowledge_entities WHERE name=?", (name,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def delete_knowledge_relation(self, relation_id: str) -> bool:
        cursor = await self._conn.execute(
            "DELETE FROM knowledge_relations WHERE id=?", (relation_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def get_all_entities(self) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM knowledge_entities ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_relations(self) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM knowledge_relations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def merge_entity(self, entity: dict):
        name = entity.get("name", "")
        if not name:
            return
        kind = entity.get("kind", "")
        new_obs = entity.get("observations", [])
        existing = await self.get_knowledge_entity(name)
        if existing:
            old_obs = existing.get("observations", [])
            if isinstance(old_obs, str):
                try:
                    old_obs = json.loads(old_obs)
                except (json.JSONDecodeError, TypeError):
                    old_obs = []
            merged = list(old_obs)
            for obs in new_obs:
                if obs not in merged:
                    merged.append(obs)
            await self._conn.execute(
                "UPDATE knowledge_entities SET kind=?, observations=?, updated_at=? WHERE name=?",
                (kind or existing.get("kind", ""), json.dumps(merged, ensure_ascii=False), time.time(), name),
            )
            await self._conn.commit()
        else:
            entity_id = entity.get("id", f"ENT-{int(time.time() % 100000):05d}")
            await self.insert_knowledge_entity(entity_id, name, kind, new_obs)

    async def merge_relation(self, relation: dict):
        from_entity = relation.get("from_entity", relation.get("source", ""))
        relation_type = relation.get("relation_type", relation.get("type", ""))
        to_entity = relation.get("to_entity", relation.get("target", ""))
        if not from_entity or not relation_type or not to_entity:
            return
        cursor = await self._conn.execute(
            "SELECT id FROM knowledge_relations WHERE from_entity=? AND relation_type=? AND to_entity=?",
            (from_entity, relation_type, to_entity),
        )
        if await cursor.fetchone():
            return
        rel_id = relation.get("id", f"REL-{int(time.time() % 100000):05d}")
        await self.insert_knowledge_relation(rel_id, from_entity, relation_type, to_entity)

    async def get_related_knowledge(self, entity_names: list[str], depth: int = 1) -> dict:
        all_entities = {}
        all_relations = []
        visited = set(entity_names)
        frontier = list(entity_names)
        for _ in range(depth):
            next_frontier = []
            for name in frontier:
                if name in all_entities:
                    continue
                ent = await self.get_knowledge_entity(name)
                if ent:
                    all_entities[name] = ent
                rels = await self.get_knowledge_relations(name, direction="both")
                for rel in rels:
                    rel_key = (rel.get("from_entity", ""), rel.get("relation_type", ""), rel.get("to_entity", ""))
                    if rel_key not in [(r.get("from_entity",""), r.get("relation_type",""), r.get("to_entity","")) for r in all_relations]:
                        all_relations.append(rel)
                    other = rel.get("to_entity") if rel.get("from_entity") == name else rel.get("from_entity")
                    if other and other not in visited:
                        visited.add(other)
                        next_frontier.append(other)
            frontier = next_frontier
        return {"entities": list(all_entities.values()), "relations": all_relations}

    async def cleanup_stale(self, days: int = 30) -> int:
        cutoff = time.time() - days * 86400
        cursor = await self._conn.execute(
            "DELETE FROM knowledge_entities WHERE updated_at < ?", (cutoff,)
        )
        await self._conn.execute(
            "DELETE FROM knowledge_relations WHERE updated_at < ?", (cutoff,)
        )
        await self._conn.commit()
        return cursor.rowcount

    async def get_entity_count(self) -> int:
        cursor = await self._conn.execute("SELECT COUNT(*) as cnt FROM knowledge_entities")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
