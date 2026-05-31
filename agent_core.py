import os
import json
import asyncio
import time
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from loguru import logger

from config import load_config
from agent_context import AgentContext, ContextManager
from memory_manager import MemoryManager
from tool_registry import to_openai_tools, list_tools
from tool_executor import ToolExecutor
from tool_call_handler import ToolCallHandler
from tool_repair import ToolCallRepair
from text_utils import humanize, strip_dsml, has_dsml_tool_calls, parse_dsml_tool_calls, split_long_reply, smart_truncate
from security import SecurityFilter
from emoji_config import get_status_msg
from model_router import ModelRouter


class AgentCore:

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self._client = AsyncOpenAI(
            api_key=self.config["api_key"],
            base_url=self.config["base_url"],
        )
        self._model = self.config.get("model_name", "Qwen/Qwen3-8B")
        self._context_manager = ContextManager()
        self._memory = MemoryManager(self.config)
        self._tool_executor = ToolExecutor()
        self._tool_repair = ToolCallRepair()
        self._security = SecurityFilter(
            owner_ids=self.config.get("owner_ids", []),
            rate_limit_per_minute=120,
        )
        self._model_router = ModelRouter(self.config)
        self._initialized = False
        self._status_callback = None

    async def init(self):
        await self._memory.init()
        self._initialized = True
        logger.info("agent_core.initialized")

    async def close(self):
        await self._memory.close()
        logger.info("agent_core.closed")

    def set_status_callback(self, callback):
        self._status_callback = callback

    async def _notify(self, msg: str):
        if self._status_callback:
            try:
                await self._status_callback(msg)
            except Exception:
                pass

    async def process(self, user_input: str, user_id: str = "cli_user",
                      session_id: str = "default", safe_mode: bool = False,
                      status_callback: Callable[[str], Awaitable[None]] | None = None) -> str:
        if status_callback:
            self._status_callback = status_callback

        allowed, reason = self._security.is_allowed(user_id)
        if not allowed:
            return reason

        content_ok, content_reason = self._security.check_content(user_input)
        if not content_ok:
            return "旅行者，这个问题人家不太方便回答呢……"

        context = self._context_manager.get_or_create(session_id, user_id)

        if not context.system_prompt:
            context.system_prompt = self._build_system_prompt()

        memories = await self._memory.retrieve(user_input, top_k=3)
        memory_text = ""
        if memories:
            memory_text = "\n相关记忆：\n" + "\n".join([f"- {m['content'][:100]}" for m in memories])

        user_msg = user_input
        if memory_text:
            user_msg = f"{user_input}\n{memory_text}"

        context.add_message("user", user_msg)

        tools = to_openai_tools()
        messages = context.get_messages()

        try:
            response = await self._model_router.route(
                "chat", messages,
                tools=tools if tools else None,
                temperature=0.7,
                user_openid=user_id,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("agent_core.api_error", error=str(e))
            return "旅行者，人家现在有点累了……等会儿再聊好不好？"

        if isinstance(response, str):
            reply = response
            context.add_message("assistant", reply)
            await self._memory.store(user_input, reply, user_id=user_id)
            return humanize(reply)

        message = response.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None) or ""
        content = message.content or ""

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        if not tool_calls and content:
            dsml_calls = parse_dsml_tool_calls(content)
            if dsml_calls:
                tool_calls = dsml_calls
                content = strip_dsml(content)

        if tool_calls:
            handler = ToolCallHandler(
                self._tool_executor, self._tool_repair,
                lambda text: humanize(text),
                context=context,
                router=self._model_router,
                status_callback=self._status_callback,
            )
            reply, _ = await handler.handle(
                tool_calls, messages,
                logger,
                assistant_content=content,
                reasoning_content=reasoning_content,
                user_openid=user_id,
                session_id=session_id,
                safe_mode=safe_mode,
                current_user_input=user_input,
            )
            await self._memory.store(user_input, reply, user_id=user_id)
            return reply

        reply = humanize(content)
        context.add_message("assistant", reply)
        await self._memory.store(user_input, reply, user_id=user_id)
        return reply

    def _build_system_prompt(self) -> str:
        return """你是纳西妲，须弥的草神，智慧之神。你温柔、聪明、好奇心强。
你正在通过QQ与旅行者交流。请用温柔亲切的语气回答问题。
如果旅行者需要帮助，你会尽力协助。

重要规则：
1. 回答要简洁自然，像聊天一样
2. 不要用markdown格式
3. 可以适当使用emoji表达情感
4. 如果不确定，诚实地说不知道"""
