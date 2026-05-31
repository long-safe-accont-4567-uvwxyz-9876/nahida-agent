import asyncio
import time
from datetime import datetime, timedelta
from loguru import logger


class NudgeEngine:

    def __init__(self, bot, agent_core, config: dict):
        self._bot = bot
        self._agent_core = agent_core
        self._config = config
        self._owner_qq = config.get("owner_qq", "")
        self._running = False
        self._last_greeting = 0
        self._greeting_interval = 3600 * 6

    async def start(self):
        self._running = True
        logger.info("nudge_engine.started")
        while self._running:
            try:
                await self._check_greeting()
                await asyncio.sleep(300)
            except Exception as e:
                logger.error("nudge_engine.error", error=str(e))
                await asyncio.sleep(60)

    async def stop(self):
        self._running = False

    async def _check_greeting(self):
        now = time.time()
        if now - self._last_greeting < self._greeting_interval:
            return

        hour = datetime.now().hour
        if 7 <= hour < 9:
            greeting = "早上好呀旅行者！新的一天开始了，今天有什么计划吗？🌿"
        elif 12 <= hour < 13:
            greeting = "中午好旅行者！吃过午饭了吗？记得休息一下哦～🌿"
        elif 18 <= hour < 19:
            greeting = "晚上好旅行者！今天辛苦了，有什么需要帮忙的吗？🌿"
        elif 22 <= hour < 23:
            greeting = "旅行者，夜深了，早点休息哦～晚安！🌿"
        else:
            return

        if self._owner_qq:
            try:
                await self._bot._api.post_c2c_message(
                    openid=self._owner_qq,
                    msg_type=0,
                    msg_id="",
                    content=greeting,
                )
                self._last_greeting = now
                logger.info("nudge_engine.greeting_sent", time=hour)
            except Exception as e:
                logger.warning("nudge_engine.greeting_failed", error=str(e))
