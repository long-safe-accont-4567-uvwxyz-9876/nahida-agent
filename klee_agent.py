import os
import asyncio
from loguru import logger
from agent_core import AgentCore
from config import load_config


class KleeAgent:

    def __init__(self, agent_core: AgentCore = None):
        self._agent_core = agent_core
        self._name = "可莉"
        self._personality = "活泼、可爱、充满好奇心的火花骑士"

    async def process(self, user_input: str, user_id: str = "") -> str:
        if self._agent_core:
            return await self._agent_core.process(
                f"[可莉任务] {user_input}",
                user_id=user_id or "klee",
                session_id=f"klee_{user_id}",
            )
        return "可莉现在在忙，等会儿再来找可莉玩吧！💥"
