import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Optional
import botpy
from botpy import logging
from botpy.message import Message, GroupMessage, C2CMessage
from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging
setup_logging()

from config import load_config
from task_orchestrator import build_task_graph, run_task_graph, TaskState
from agent_dispatcher import AgentDispatcher, AgentConfig
from agent_core import AgentCore
from text_utils import split_long_reply, smart_truncate
from emoji_config import get_status_msg
from knowledge_graph import KnowledgeGraph
from nudge_engine import NudgeEngine
from portrait_manager import PortraitManager
from sticker_manager import StickerManager
from file_receiver import FileReceiver

logger = logging.get_logger()


class AIQQBot(botpy.Client):

    def __init__(self):
        intents = botpy.Intents.none()
        intents.public_messages = True
        intents.direct_message = True
        super().__init__(intents=intents)
        self.config = load_config()
        self._agent_core: Optional[AgentCore] = None
        self._dispatcher: Optional[AgentDispatcher] = None
        self._task_graph = None
        self._nudge_engine: Optional[NudgeEngine] = None
        self._knowledge_graph: Optional[KnowledgeGraph] = None
        self._portrait_manager: Optional[PortraitManager] = None
        self._sticker_manager: Optional[StickerManager] = None
        self._file_receiver: Optional[FileReceiver] = None
        self._ready = False

    async def on_ready(self):
        logger.info("bot.ready", user=self.robot.name)
        await self._init_components()
        self._ready = True

    async def _init_components(self):
        self._agent_core = AgentCore(self.config)
        await self._agent_core.init()

        self._dispatcher = AgentDispatcher(self.config)
        agents = [
            AgentConfig(
                name="xilian",
                display_name="希兰",
                personality_file="xilian_personality.md",
                capabilities=["search", "browse", "analyze", "discover"],
                route_description="搜索信息、查找资料、浏览网页、信息探索",
            ),
            AgentConfig(
                name="yinlang",
                display_name="银狼",
                personality_file="yinlang_personality.md",
                capabilities=["code", "shell", "debug", "deploy", "hardware"],
                route_description="编程开发、代码调试、系统运维、硬件控制",
            ),
            AgentConfig(
                name="nike",
                display_name="妮可",
                personality_file="nike_personality.md",
                capabilities=["research", "analysis", "math", "science"],
                route_description="学术研究、深度分析、数学推导、科学研究",
                model_tier="pro",
            ),
            AgentConfig(
                name="keli",
                display_name="可莉",
                personality_file="klee_personality.md",
                capabilities=["chat", "play", "simple_tasks"],
                route_description="简单任务、陪聊、日常助手",
            ),
        ]
        for agent_cfg in agents:
            self._dispatcher.register(agent_cfg)

        client = self._agent_core._model_router.get_client()
        model = self._agent_core._model_router.model
        self._task_graph = build_task_graph(
            self._dispatcher,
            self._dispatcher.agent_configs,
            client,
            model,
            nahida_chat_callback=lambda prompt: self._agent_core.process(prompt, user_id="system"),
        )

        self._knowledge_graph = KnowledgeGraph(self.config)
        await self._knowledge_graph.init()

        self._portrait_manager = PortraitManager(self.config)
        self._sticker_manager = StickerManager()
        self._file_receiver = FileReceiver()

        if self.config.get("owner_qq"):
            self._nudge_engine = NudgeEngine(self, self._agent_core, self.config)
            asyncio.create_task(self._nudge_engine.start())

        logger.info("bot.components_initialized")

    async def on_c2c_message_create(self, message: C2CMessage):
        if not self._ready:
            return
        user_openid = message.author.user_openid
        content = message.content.strip()
        if not content:
            return

        if content.startswith("/"):
            await self._handle_command(message, content, user_openid)
            return

        async def status_callback(msg: str):
            try:
                await message._api.post_c2c_message(
                    openid=user_openid,
                    msg_type=0,
                    msg_id=message.id,
                    content=msg,
                )
            except Exception:
                pass

        try:
            state = await run_task_graph(
                self._task_graph,
                content,
                user_openid,
                session_id=f"c2c_{user_openid}",
                status_callback=status_callback,
                agent_configs=self._dispatcher.agent_configs,
                dispatcher=self._dispatcher,
            )
            reply = state.final_output or state.sub_agent_reply or "旅行者，人家没听懂呢……"
            await self._send_reply(message, reply, user_openid)
        except Exception as e:
            logger.error("bot.process_error", error=str(e))
            await self._send_reply(message, "旅行者，人家出了点小问题……", user_openid)

    async def _handle_command(self, message: C2CMessage, content: str, user_openid: str):
        cmd = content.lower().strip()
        if cmd == "/help":
            reply = "🌿 可用命令：\n/help - 帮助\n/status - 状态\n/memory - 记忆\n/tools - 工具列表"
        elif cmd == "/status":
            reply = f"🌿 系统正常运行中\n模型: {self.config.get('model_name')}"
        elif cmd == "/memory":
            memories = await self._agent_core._memory.get_recent(5)
            if memories:
                reply = "🌿 最近记忆：\n" + "\n".join([f"- {m['content'][:50]}" for m in memories])
            else:
                reply = "🌿 暂无记忆"
        elif cmd == "/tools":
            from tool_registry import list_tools
            tools = list_tools()
            reply = "🌿 可用工具：\n" + "\n".join([f"- {t['name']}: {t['description'][:30]}" for t in tools])
        else:
            reply = "🌿 未知命令，输入 /help 查看帮助"
        await self._send_reply(message, reply, user_openid)

    async def _send_reply(self, message: C2CMessage, reply: str, user_openid: str):
        segments = split_long_reply(reply)
        for seg in segments:
            seg = smart_truncate(seg)
            try:
                await message._api.post_c2c_message(
                    openid=user_openid,
                    msg_type=0,
                    msg_id=message.id,
                    content=seg,
                )
            except Exception as e:
                logger.error("bot.send_failed", error=str(e))

    async def on_group_at_message_create(self, message: GroupMessage):
        if not self._ready:
            return
        content = message.content.strip()
        if not content:
            return
        group_openid = message.group_openid
        member_openid = message.author.member_openid

        async def status_callback(msg: str):
            pass

        try:
            state = await run_task_graph(
                self._task_graph,
                content,
                member_openid,
                session_id=f"group_{group_openid}",
                status_callback=status_callback,
                agent_configs=self._dispatcher.agent_configs,
                dispatcher=self._dispatcher,
            )
            reply = state.final_output or state.sub_agent_reply or "旅行者，人家没听懂呢……"
            segments = split_long_reply(reply)
            for seg in segments:
                seg = smart_truncate(seg)
                await message._api.post_group_message(
                    group_openid=group_openid,
                    msg_type=0,
                    msg_id=message.id,
                    content=seg,
                )
        except Exception as e:
            logger.error("bot.group_error", error=str(e))


async def main():
    config = load_config()
    app_id = config.get("app_id")
    app_secret = config.get("app_secret")
    if not app_id or not app_secret:
        print("请配置 APP_ID 和 APP_SECRET")
        return
    bot = AIQQBot()
    await bot.start(appid=app_id, secret=app_secret)


if __name__ == "__main__":
    asyncio.run(main())
