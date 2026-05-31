import os
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Any
from loguru import logger

MAX_HISTORY = 50
MAX_CONTEXT_TOKENS = 8000


class AgentContext:

    def __init__(self, session_id: str = "default", owner_id: str = ""):
        self.session_id = session_id
        self.owner_id = owner_id
        self.messages: list[dict] = []
        self._system_prompt = ""
        self._system_prompt_loader = None
        self._metadata: dict[str, Any] = {}
        self._created_at = time.time()
        self._last_active = time.time()

    @property
    def system_prompt(self) -> str:
        if self._system_prompt:
            return self._system_prompt
        if self._system_prompt_loader:
            try:
                return self._system_prompt_loader()
            except Exception:
                pass
        return ""

    @system_prompt.setter
    def system_prompt(self, value: str):
        self._system_prompt = value

    def set_system_prompt_loader(self, loader):
        self._system_prompt_loader = loader

    def add_message(self, role: str, content: str, **kwargs):
        msg = {"role": role, "content": content}
        msg.update(kwargs)
        self.messages.append(msg)
        self._last_active = time.time()
        self._trim()

    def get_messages(self, include_system: bool = True) -> list[dict]:
        result = []
        if include_system:
            sp = self.system_prompt
            if sp:
                result.append({"role": "system", "content": sp})
        result.extend(self.messages)
        return result

    def clear(self):
        self.messages.clear()
        logger.info("context.cleared", session=self.session_id)

    def _trim(self):
        if len(self.messages) > MAX_HISTORY * 2:
            self.messages = self.messages[-(MAX_HISTORY * 2):]

    @property
    def is_expired(self) -> bool:
        return time.time() - self._last_active > 3600

    def set_metadata(self, key: str, value: Any):
        self._metadata[key] = value

    def get_metadata(self, key: str, default=None):
        return self._metadata.get(key, default)


class ContextManager:

    def __init__(self, max_sessions: int = 100):
        self._contexts: dict[str, AgentContext] = {}
        self._max_sessions = max_sessions

    def get_or_create(self, session_id: str, owner_id: str = "") -> AgentContext:
        if session_id not in self._contexts:
            self._contexts[session_id] = AgentContext(session_id, owner_id)
            self._cleanup()
        ctx = self._contexts[session_id]
        ctx._last_active = time.time()
        return ctx

    def _cleanup(self):
        if len(self._contexts) <= self._max_sessions:
            return
        sorted_ctx = sorted(self._contexts.items(), key=lambda x: x[1]._last_active)
        to_remove = len(self._contexts) - self._max_sessions
        for sid, _ in sorted_ctx[:to_remove]:
            del self._contexts[sid]

    def get_stats(self) -> dict:
        return {
            "active_sessions": len(self._contexts),
            "max_sessions": self._max_sessions,
        }
