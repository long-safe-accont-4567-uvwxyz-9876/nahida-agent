import os
import sys
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from logging_config import setup_logging
setup_logging()

from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, AGENT_CONFIG, WORKSPACE_DIR, STICKER_DIR, KLEE_STICKER_DIR, FILE_DIR, build_system_prompt
from model_router import ModelRouter
from agent_context import AgentContext
from database import DatabaseManager
from security import SecurityFilter
from tool_registry import to_openai_tools, get_tool, clear_tools
from tool_executor import ToolExecutor
from tool_repair import ToolCallRepair
from memory_manager import MemoryManager
from vector_store import VectorStore
from emotion_simple import detect_emotion, build_emotion_hint
from result_wrapper import ResultWrapper
from text_utils import smart_truncate, strip_dsml, has_dsml_tool_calls, parse_dsml_tool_calls, humanize
from portrait_manager import PortraitManager
from notebook_manager import NotebookManager
from learning_manager import LearningManager
from slash_commands import SlashCommandHandler
from smart_error_handler import get_error_handler
from knowledge_graph import KnowledgeGraph
from sticker_manager import StickerManager
from file_receiver import FileReceiver
from tool_call_handler import ToolCallHandler
from klee_agent import KleeAgent
from tts_engine import TTSEngine
from agent_dispatcher import AgentDispatcher, SubAgentConfig
from task_orchestrator import TaskGraph, build_task_graph, run_task_graph
from emoji_config import get_status_msg

import tools.file_tools_v2
import tools.code_tools_v2
import tools.web_tools_v2
import tools.document_tools
import tools.web_browse_tools
import tools.multi_search_tools
import tools.hardware_tools
import tools.vision_tools
import tools.system_tools


def _extract_reasoning_content(response: Any) -> str | None:
    try:
        message = response.choices[0].message
        if hasattr(message, "reasoning_content"):
            return message.reasoning_content
        if hasattr(message, "model_extra") and isinstance(message.model_extra, dict):
            return message.model_extra.get("reasoning_content")
        if isinstance(message, dict):
            return message.get("reasoning_content")
    except (AttributeError, IndexError):
        pass
    return None


def _extract_delta_reasoning_content(chunk_dict: dict) -> str | None:
    try:
        delta = chunk_dict.get("choices", [{}])[0].get("delta", {})
        return delta.get("reasoning_content")
    except (IndexError, AttributeError):
        pass
    return None


DEGRADED_REPLY = "嗯……人家现在有点不太舒服，等会儿再聊好不好？"

_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@dataclass
class ProcessResult:
    reply: str
    emotion: str = ""
    sticker_path: Path | None = None
    audio_path: Path | None = None
    tool_results: list = field(default_factory=list)


class AgentCore:
    def __init__(self):
        self.router = ModelRouter()
        self.db = DatabaseManager()
        _owner_ids = os.getenv("OWNER_IDS", "").split(",")
        _owner_ids = [x.strip() for x in _owner_ids if x.strip()]
        self.security = SecurityFilter(owner_ids=_owner_ids)
        self.context = AgentContext(system_prompt_loader=build_system_prompt)
        self.tool_executor = ToolExecutor(db=self.db)
        self.tool_repair = ToolCallRepair(
            allowed_tool_names=set(t["function"]["name"] for t in to_openai_tools())
        )
        self.result_wrapper = ResultWrapper(router=self.router)
        self.memory: MemoryManager | None = None
        self.portrait_manager: PortraitManager | None = None
        self.notebook_manager: NotebookManager | None = None
        self.learning_manager: LearningManager | None = None
        self.slash_handler: SlashCommandHandler | None = None
        self._initialized = False
        self._current_session_id: str = ""
        self._current_user_openid: str = ""
        self._current_user_input: str = ""
        self._handled_by_tool_call = False
        self._last_user_emotion: str = ""
        self.sticker_manager = StickerManager(STICKER_DIR)
        self.klee_sticker_manager = StickerManager(KLEE_STICKER_DIR)
        self.file_receiver = FileReceiver(FILE_DIR)
        self.klee = KleeAgent(tool_executor=self.tool_executor, tool_repair=self.tool_repair, nahida_delegate=self._nahida_delegate_for_klee)
        self.tts = TTSEngine()
        self.dispatcher = AgentDispatcher(
            tts=self.tts,
            tool_executor=self.tool_executor,
            tool_repair=self.tool_repair,
            delegate_callback=self._nahida_delegate_for_klee,
        )
        self._task_graph: TaskGraph | None = None
        self._agent_route_configs: dict = {}
        self._tool_call_handler = ToolCallHandler(self.tool_executor, self.tool_repair, self._clean_reply, self.context, self.router, klee_delegate=self.delegate_to_klee, agent_name="nahida", personality_file=str(Path(__file__).parent / "nahida_personality.md"))
        self._status_callback = None
        self._user_chat_target: dict[str, str] = {}
        self._delegate_depth = 0
        self._voice_mode: bool = False
        self._error_handler = None

    async def init(self) -> None:
        await self._init_infrastructure()
        await self._init_cognitive()
        await self.klee.init()
        await self.tts.init()
        keli_config = SubAgentConfig(
            name="keli",
            display_name="可莉",
            provider="mimo",
            model="mimo-v2.5-pro",
            personality_file=str(Path(__file__).parent / "klee_personality.md"),
            voice_ref="keli",
            excluded_tools={"call_klee", "shell_command", "python_executor", "write_file", "search_files", "read_file", "list_files", "web_browse", "document_reader", "multi_search", "wolfram_query"},
            base_url="https://api.xiaomimimo.com/v1",
            api_key_env="MIMO_API_KEY",
            capabilities=["chat", "play", "fun"],
            route_description="日常聊天、玩耍、轻松有趣的对话",
        )
        await self.dispatcher.register(keli_config)
        yinlang_config = SubAgentConfig(
            name="yinlang",
            display_name="银狼",
            provider="mimo",
            model="mimo-v2.5-pro",
            personality_file=str(Path(__file__).parent / "yinlang_personality.md"),
            voice_ref=None,
            excluded_tools={"call_klee", "call_nahida"},
            base_url="https://api.xiaomimimo.com/v1",
            api_key_env="MIMO_API_KEY",
            capabilities=["coding", "debug", "script", "programming", "hardware", "system", "devops"],
            route_description="编程、代码编写、调试、技术问题、硬件控制、系统运维、开发辅助",
        )
        await self.dispatcher.register(yinlang_config)
        xilian_config = SubAgentConfig(
            name="xilian",
            display_name="昔涟",
            provider="mimo",
            model="mimo-v2.5-pro",
            personality_file=str(Path(__file__).parent / "xilian_personality.md"),
            voice_ref=None,
            excluded_tools={"call_klee", "call_nahida", "shell_command", "python_executor", "write_file"},
            base_url="https://api.xiaomimimo.com/v1",
            api_key_env="MIMO_API_KEY",
            capabilities=["search", "lookup", "query", "explore", "discover"],
            route_description="搜索信息、查询资料、探索发现",
        )
        await self.dispatcher.register(xilian_config)
        nike_config = SubAgentConfig(
            name="nike",
            display_name="尼可",
            provider="mimo",
            model="mimo-v2.5-pro",
            personality_file=str(Path(__file__).parent / "nike_personality.md"),
            voice_ref=None,
            excluded_tools={"call_klee", "call_nahida", "shell_command", "write_file"},
            base_url="https://api.xiaomimimo.com/v1",
            api_key_env="MIMO_API_KEY",
            capabilities=["research", "analysis", "study", "academic"],
            route_description="研究分析、学术思考、深度解读",
        )
        await self.dispatcher.register(nike_config)
        from openai import AsyncOpenAI as _AOI
        route_client = _AOI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL,
        )
        for name, agent in self.dispatcher._agents.items():
            self._agent_route_configs[name] = {
                "display_name": agent.config.display_name,
                "capabilities": agent.config.capabilities,
                "route_description": agent.config.route_description,
            }
        self._task_graph = build_task_graph(
            dispatcher=self.dispatcher,
            agent_configs=self._agent_route_configs,
            route_client=route_client,
            nahida_chat_callback=self._nahida_synthesis_chat,
        )
        await self._init_interaction()
        self._initialized = True
        logger.info("agent_core.initialized")

    async def _init_infrastructure(self) -> None:
        await self.db.init()
        self.router.set_db(self.db, analytics=self.db.analytics)
        embed_api_key = os.getenv("EMBED_API_KEY", "")
        embed_base_url = os.getenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
        self._vec_store = None
        if embed_api_key:
            try:
                self._vec_store = VectorStore(
                    db_path=str(self.db.db_path).replace(".db", "_vec.db"),
                    embed_api_key=embed_api_key,
                    embed_base_url=embed_base_url,
                )
                await self._vec_store.init()
                logger.info("vector_store.enabled")
            except Exception as e:
                logger.warning(f"vector_store.init_failed: {e}")
                self._vec_store = None

    async def _init_cognitive(self) -> None:
        self.memory = MemoryManager(
            db=self.db,
            memory=self.db.memory,
            vector_store=self._vec_store,
            router=self.router,
        )
        self.knowledge_graph = KnowledgeGraph(db=self.db, knowledge_db=self.db.knowledge, router=self.router)
        self.memory.set_knowledge_graph(self.knowledge_graph)
        self.notebook_manager = NotebookManager(db=self.db, notebook=self.db.notebook, router=self.router)
        self.learning_manager = LearningManager(db=self.db, learning=self.db.learning, router=self.router)
        self.portrait_manager = PortraitManager(db=self.db, memory=self.db.memory, router=self.router, notebook=self.db.notebook)

    async def _init_interaction(self) -> None:
        self._error_handler = get_error_handler(
            db=self.db,
            dispatcher=self.dispatcher,
        )
        learning_additions = await self.learning_manager.get_system_prompt_additions()
        if learning_additions:
            self.context.learned_rules = learning_additions
        portrait = await self.portrait_manager.get_current_portrait()
        if portrait and portrait.get("content"):
            self.context.user_portrait = portrait["content"]
            logger.info("portrait.loaded", version=portrait.get("version"))
        await self._load_notebook_context()
        await self.context.restore_from_db(self.db)
        self.slash_handler = SlashCommandHandler(
            db=self.db,
            router=self.router,
            context=self.context,
            memory=self.memory,
            learning_manager=self.learning_manager,
            notebook_manager=self.notebook_manager,
            security=self.security,
            agent=self,
        )

    async def process(self, user_input: str, user_id: str = "qq_user",
                      source: str = "qq",
                      user_openid: str = "",
                      session_id: str = "",
                      status_callback=None) -> ProcessResult:
        if not self._initialized:
            return ProcessResult(reply=DEGRADED_REPLY)

        self._status_callback = status_callback

        trace = logger.bind(trace_id=f"{int(time.time()*1000)%1000000:06d}")
        trace.info("agent.process.start", source=source, user_id=user_id,
                    msg_preview=user_input[:80])

        allowed, reason = self.security.is_allowed(user_id)
        if not allowed:
            trace.warning("agent.blocked", reason=reason)
            return ProcessResult(reply="")

        content_ok, content_reason = self.security.check_content(user_input)
        if not content_ok:
            trace.warning("agent.content_blocked", reason=content_reason)
            return ProcessResult(reply="嗯？你说的什么呀，我没有听懂～")

        if self.slash_handler and self.slash_handler.is_slash_command(user_input):
            slash_reply = await self.slash_handler.handle(user_input, user_id)
            return ProcessResult(reply=slash_reply)

        chat_targets = self._parse_chat_target(user_input, user_id)
        clean_input = re.sub(r'@[可莉纳西妲]+', '', user_input).strip()

        if not clean_input:
            target_name = "可莉" if chat_targets and chat_targets[0] == "keli" else "纳西妲"
            confirm_msg = f"好～现在跟{target_name}说话啦！有什么想聊的呀？"
            trace.info("agent.chat_target_switch", target=chat_targets)
            return ProcessResult(reply=confirm_msg, emotion="greeting")

        non_nahida_targets = [t for t in chat_targets if t != "nahida"]
        if non_nahida_targets:
            if len(non_nahida_targets) == 1:
                return await self._dispatch_single_sub_agent(
                    non_nahida_targets[0], clean_input, user_id, source, session_id, trace,
                )
            else:
                return await self._dispatch_parallel_sub_agents(
                    non_nahida_targets, clean_input, user_id, source, session_id, trace,
                )

        if "nahida" in chat_targets and self._task_graph and not self._is_manual_target(user_input, user_id) and not self._is_simple_task(clean_input):
            try:
                graph_result = await run_task_graph(
                    graph=self._task_graph,
                    user_input=clean_input,
                    user_id=user_id,
                    session_id=session_id,
                    status_callback=status_callback,
                    agent_configs=self._agent_route_configs,
                    dispatcher=self.dispatcher,
                )
                if graph_result.final_output:
                    emotion = detect_emotion(clean_input)
                    self._last_user_emotion = emotion.get("primary", "")
                    asyncio.create_task(self._background_tasks(
                        clean_input, graph_result.final_output, user_id, source, emotion, [],
                        session_id=session_id,
                    ))
                    emotion_label = emotion.get("primary", "")
                    clean_reply = self.klee_sticker_manager.strip_emotion_tag(graph_result.final_output)
                    sticker_path = None
                    audio_path = None
                    if self._voice_mode and len(clean_reply) > 2:
                        try:
                            target_agent = self.dispatcher.get_agent(graph_result.route_target)
                            if target_agent:
                                audio_path = await target_agent.synthesize(clean_reply)
                        except Exception as e:
                            logger.warning("agent.routed_tts_failed", error=str(e))
                    return ProcessResult(reply=clean_reply, emotion=emotion_label, sticker_path=sticker_path, audio_path=audio_path)
            except Exception as e:
                logger.warning("agent.task_graph_failed", error=str(e))
                return ProcessResult(reply=DEGRADED_REPLY)

        if "可莉" in user_input and "nahida" in chat_targets:
            klee_reply = await self.delegate_to_klee(clean_input, factual=True)
            self.context.klee_context = klee_reply
        else:
            self.context.klee_context = None

        emotion = detect_emotion(user_input)
        emotion_hint = build_emotion_hint(emotion)
        self.context.emotion_hint = emotion_hint
        self._last_user_emotion = emotion.get("primary", "")

        if self.memory:
            self.memory.signal_new_message()
            try:
                memories = await self.memory.retrieve_memories(user_input, k=3)
                self.context.memory_retrieval = memories if memories else None
            except Exception as e:
                logger.warning("memory.retrieve_failed", error=str(e))
                self.context.memory_retrieval = None

        await self._load_notebook_context()

        messages = self.context.build_messages(user_input)

        _sticker_keywords = ["表情包", "表情", "贴纸", "sticker", "贴图"]
        _sticker_intent = any(kw in clean_input for kw in _sticker_keywords)
        _pre_picked_sticker = None
        if _sticker_intent and self.sticker_manager.available:
            _detected_e = self.sticker_manager.detect_emotion(clean_input)
            if not _detected_e:
                _emap = {"喜悦": "happy", "悲伤": "sad", "焦虑": "sad", "平静": "", "愤怒": "angry", "好奇": "curious"}
                _detected_e = _emap.get(emotion.get("primary", ""), "happy")
            _pre_picked_sticker = self.sticker_manager.pick(_detected_e)
            if _pre_picked_sticker:
                _sticker_desc = _pre_picked_sticker.stem.replace("_", " ").replace("-", " ")
                _sticker_cat = _pre_picked_sticker.parent.name
                messages.append({
                    "role": "system",
                    "content": f"[系统提示] 你正在给用户发送一张表情包图片。图片描述：「{_sticker_desc}」，分类：「{_sticker_cat}」。请在回复中自然地提到这张表情包的内容，让用户感受到你真的知道发了什么图。不要说'这是一张图片'之类的机械描述，要用你的风格自然表达。"
                })

        tools = to_openai_tools() if to_openai_tools() else None

        should_escalate, reason = self._should_escalate_to_pro(user_input, tools)
        base_task = "chat_pro" if should_escalate else "chat"
        task_type = self.router.resolve_task_type(base_task)

        if should_escalate:
            trace.info("chat.escalated_to_pro", reason=reason)

        reply = ""
        tool_results = []
        self._current_user_input = user_input
        self._handled_by_tool_call = False

        _model_cfg = AGENT_CONFIG.get("model", {})
        is_owner = self.security.is_owner(user_id)

        try:
            result = await self.router.route(
                task_type,
                messages,
                temperature=_model_cfg.get("temperature", 0.7),
                tools=tools,
                tool_choice="auto" if tools else None,
                user_openid=user_openid,
                session_id=session_id,
            )

            if isinstance(result, str):
                if has_dsml_tool_calls(result) and tools:
                    dsml_calls = parse_dsml_tool_calls(result, self.tool_repair._allowed_tools)
                    if dsml_calls:
                        logger.info("agent.dsml_in_content", count=len(dsml_calls))
                        for dc in dsml_calls:
                            fn = dc.get("function", {})
                            logger.info("agent.dsml_tool_call", tool=fn.get("name",""), args=str(fn.get("arguments",""))[:200])
                        dsml_reasoning = self.router.pop_reasoning_content()
                        reply, tool_results = await self._handle_tool_calls(
                            dsml_calls, messages, trace,
                            assistant_content=result,
                            reasoning_content=dsml_reasoning,
                            user_openid=user_openid, session_id=session_id,
                            safe_mode=not is_owner,
                        )
                        self._handled_by_tool_call = True
                        logger.info("agent.got_dsml_tool_reply", length=len(reply), preview=reply[:80])
                    else:
                        reply = self._clean_reply(result)
                        logger.info("agent.got_string_reply", length=len(reply), preview=reply[:80])
                else:
                    reply = self._clean_reply(result)
                    logger.info("agent.got_string_reply", length=len(reply), preview=reply[:80])
            else:
                msg = result.choices[0].message
                if msg.tool_calls:
                    tc_list = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                    reasoning = getattr(msg, "reasoning_content", None)
                    reply, tool_results = await self._handle_tool_calls(
                        tc_list, messages, trace,
                        assistant_content=msg.content or "",
                        reasoning_content=reasoning,
                        user_openid=user_openid, session_id=session_id,
                        safe_mode=not is_owner,
                    )
                    self._handled_by_tool_call = True
                    logger.info("agent.got_tool_reply", length=len(reply), preview=reply[:80])
                else:
                    reply = self._clean_reply(msg.content or "")
                    logger.info("agent.got_string_reply", length=len(reply), preview=reply[:80])
        except Exception as e:
            trace.error("agent.model_error", error=str(e))
            if self._error_handler:
                try:
                    error_reply = await self._error_handler.handle_error_with_intelligence(
                        error=e, user_query=user_input, context="主处理流程模型调用错误"
                    )
                    if error_reply and len(error_reply) > 50:
                        reply = error_reply
                    else:
                        reply = DEGRADED_REPLY
                except Exception:
                    reply = DEGRADED_REPLY
            else:
                try:
                    result = await self.router.route(
                        "chat_flash", messages, temperature=0.7,
                        user_openid=user_openid, session_id=session_id,
                    )
                    reply = self._clean_reply(result) if isinstance(result, str) else DEGRADED_REPLY
                except Exception:
                    reply = DEGRADED_REPLY

        if not self._handled_by_tool_call:
            self.context.add_message("user", user_input)
            self.context.add_message("assistant", reply)

        asyncio.create_task(self._background_tasks(
            user_input, reply, user_id, source, emotion, tool_results,
            session_id=session_id,
        ))

        try:
            await self.router.flush_costs()
        except Exception:
            pass

        trace.info("agent.process.done", reply_preview=reply[:100])

        emotion_label = emotion.get("primary", "")
        if _pre_picked_sticker:
            clean_reply = self.sticker_manager.strip_emotion_tag(reply)
            sticker_path = _pre_picked_sticker
        else:
            clean_reply, sticker_path = self.get_sticker_info(reply, self._last_user_emotion)

        audio_path = None
        if self._voice_mode and self.tts.available and len(clean_reply) > 2:
            try:
                audio_path = await self.tts.synthesize_nahida(clean_reply)
            except Exception as e:
                logger.warning("agent.tts_failed", error=str(e))

        return ProcessResult(reply=clean_reply, emotion=emotion_label, sticker_path=sticker_path, audio_path=audio_path, tool_results=tool_results)

    async def process_text(self, user_input: str, user_openid: str = "cli", session_id: str = "cli") -> str:
        result = await self.process(user_input, user_id="cli_owner", source="cli", user_openid=user_openid, session_id=session_id)
        return result.reply

    def _should_escalate_to_pro(self, user_msg: str, tools: list | None) -> tuple[bool, str]:
        tool_keywords = {"天气", "温度", "下雨", "搜索", "查一下", "帮我查",
                         "你还记得", "写代码", "调试", "执行", "计算"}
        if tools and any(kw in user_msg for kw in tool_keywords):
            return True, "tool_likely_query"

        negative = {"难过", "伤心", "崩溃", "绝望", "痛苦", "焦虑", "害怕",
                    "孤独", "想哭", "受不了"}
        if any(kw in user_msg for kw in negative) and len(user_msg) > 30:
            return True, "deep_emotional_content"

        if len(user_msg) > 300:
            return True, "long_complex_message"

        return False, ""

    async def _handle_tool_calls(self, tool_calls: list[dict], messages: list[dict],
                                  trace, *,
                                  assistant_content: str = "",
                                  reasoning_content: str | None = None,
                                  user_openid: str = "",
                                  session_id: str = "",
                                  safe_mode: bool = False) -> tuple[str, list]:
        self._tool_call_handler.set_status_callback(self._status_callback)
        return await self._tool_call_handler.handle(tool_calls, messages, trace, assistant_content=assistant_content, reasoning_content=reasoning_content, user_openid=user_openid, session_id=session_id, safe_mode=safe_mode, current_user_input=self._current_user_input)

    async def _background_tasks(self, user_input: str, reply: str,
                                 user_id: str, source: str,
                                 emotion: dict, tool_results: list,
                                 session_id: str = "") -> None:
        try:
            await self.db.insert_conversation_log(
                user_id=user_id,
                source=source,
                user_message=user_input,
                assistant_reply=reply,
                emotion_label=emotion.get("primary", ""),
            )
        except Exception as e:
            logger.warning("bg.conversation_log_failed", error=str(e))

        if session_id:
            try:
                await self.db.update_session(session_id)
            except Exception as e:
                logger.warning("bg.session_update_failed", error=str(e))

        if self.memory and len(self.context.history) >= 4:
            try:
                ctx = {
                    "exchanges": self.context.get_last_n(6),
                    "emotion": emotion,
                }
                await self.memory.try_idle_encode(ctx)
            except Exception as e:
                logger.warning("bg.memory_encode_failed", error=str(e))

        if self.notebook_manager:
            _spawn(self.notebook_manager.auto_note_after_message(user_input, reply))

        if self.portrait_manager:
            self.portrait_manager.mark_dirty()

        if self.portrait_manager and len(self.context.history) >= 4:
            _spawn(self._portrait_cold_start())

        if self.learning_manager:
            _spawn(
                self.learning_manager.evaluate_after_conversation(user_input, reply, tool_results)
            )

        _spawn(self._auto_archive_sessions())

    async def _auto_archive_sessions(self) -> None:
        try:
            archived = await self.db.auto_archive_stale_sessions(idle_seconds=3600)
            if archived > 0:
                logger.info("session.auto_archived", count=archived)
        except Exception as e:
            logger.warning("session.auto_archive_failed", error=str(e))

    async def _portrait_cold_start(self) -> None:
        try:
            result = await self.portrait_manager.ensure_exists()
            if result:
                self.context.user_portrait = result
                logger.info("portrait.cold_start_done", length=len(result))
        except Exception as e:
            logger.warning("portrait.cold_start_failed", error=str(e))

    async def _load_notebook_context(self) -> None:
        try:
            focus = await self.notebook_manager.get_current_focus()
            if focus:
                self.context.notebook_focus = focus

            tasks = await self.notebook_manager.get_pending_tasks_summary()
            if tasks:
                self.context.pending_tasks = tasks
        except Exception as e:
            logger.warning("notebook.context_load_failed", error=str(e))

    def _clean_reply(self, text: str) -> str:
        text = text.strip()
        prefixes = ["昔涟：", "纳西妲：", "助手：", "AI："]
        for p in prefixes:
            if text.startswith(p):
                text = text[len(p):].strip()
        text = strip_dsml(text)
        text = humanize(text, style="nahida")
        return text

    def get_sticker_info(self, reply: str, user_emotion: str = "", force_sticker: bool = False) -> tuple[str, Path | None]:
        clean_reply = self.sticker_manager.strip_emotion_tag(reply)
        sticker_path = None
        if self.sticker_manager.available:
            if force_sticker:
                detected = self.sticker_manager.detect_emotion(clean_reply) or "happy"
                sticker_path = self.sticker_manager.pick(detected)
            else:
                detected = self.sticker_manager.detect_emotion(clean_reply)
                if not detected and user_emotion:
                    user_emotion_map = {"喜悦": "happy", "悲伤": "sad", "焦虑": "sad", "平静": ""}
                    detected = user_emotion_map.get(user_emotion, "")
                if self.sticker_manager.should_send(clean_reply, detected_emotion=detected):
                    sticker_path = self.sticker_manager.pick(detected)
        return clean_reply, sticker_path

    async def _dispatch_single_sub_agent(self, target: str, clean_input: str,
                                          user_id: str, source: str, session_id: str, trace) -> ProcessResult:
        sub_agent = self.dispatcher.get_agent(target)
        if not sub_agent or not sub_agent.available:
            return ProcessResult(reply=f"{sub_agent.config.display_name if sub_agent else target}现在有点累了...等会儿再来吧！💤")

        display_name = sub_agent.config.display_name
        trace.info("agent.chat_target_sub", target=target, input_preview=clean_input[:50])
        sub_reply = await self.dispatcher.dispatch(target, clean_input, status_callback=self._status_callback)
        if sub_reply is None:
            sub_reply = f"{display_name}现在有点累了...等会儿再来吧！💤"

        emotion = detect_emotion(clean_input)
        self._last_user_emotion = emotion.get("primary", "")
        asyncio.create_task(self._background_tasks(
            clean_input, sub_reply, user_id, source, emotion, [],
            session_id=session_id,
        ))

        clean_sub_reply = self.klee_sticker_manager.strip_emotion_tag(sub_reply)

        if self.router:
            try:
                nahida_prompt = getattr(self.context, "system_prompt", "") or ""
                if not nahida_prompt and hasattr(self.context, "_system_prompt_loader") and self.context._system_prompt_loader:
                    try:
                        nahida_prompt = self.context._system_prompt_loader()
                    except Exception:
                        pass
                if not nahida_prompt:
                    nahida_prompt = "你是纳西妲，须弥的草神。"

                summary = await self.router.route(
                    "chat",
                    [
                        {"role": "system", "content": nahida_prompt},
                        {"role": "user", "content": f"用户请求：{clean_input}"},
                        {"role": "assistant", "content": f"（{display_name}的执行结果如下）\n\n{clean_sub_reply}"},
                        {"role": "user", "content": f'请基于{display_name}的结果，用纳西妲的风格向用户汇报。要求：\n1. 提取关键信息，不要直接复制原始数据\n2. 用自然语言解释数据含义\n3. 如果有异常情况要指出\n4. 保持简洁\n5. ⚠️ 如果{display_name}返回的数据明显不完整（比如只有几个字、只有\'Listing...\'或\'Done\'、或者看起来像是未完成的输出），不要编造内容，而是如实告诉用户：{display_name}那边好像没传回完整的数据，建议让{display_name}重新执行一次。'},
                    ],
                    temperature=0.7,
                    max_tokens=1024,
                )
                if isinstance(summary, str) and summary.strip():
                    clean_sub_reply = self._clean_reply(summary)
            except Exception as e:
                logger.warning("agent.sub_synthesis_failed", error=str(e))

        emotion_label = emotion.get("primary", "")
        sticker_path = None

        sub_audio_path = None
        if self._voice_mode and len(clean_sub_reply) > 2:
            try:
                sub_audio_path = await sub_agent.synthesize(clean_sub_reply)
            except Exception as e:
                logger.warning("agent.sub_tts_failed", target=target, error=str(e))

        return ProcessResult(reply=clean_sub_reply, emotion=emotion_label, sticker_path=sticker_path, audio_path=sub_audio_path)

    async def _dispatch_parallel_sub_agents(self, targets: list[str], clean_input: str,
                                            user_id: str, source: str, session_id: str, trace) -> ProcessResult:
        trace.info("agent.parallel_dispatch", targets=targets, input_preview=clean_input[:50])

        if self._status_callback:
            try:
                await self._status_callback(f"⚡ 并行调度中，同时启动 {len(targets)} 个Agent...")
            except Exception:
                pass

        agent_configs = self._agent_route_configs
        sub_tasks = {}
        for t in targets:
            desc = agent_configs.get(t, {}).get("route_description", t)
            sub_tasks[t] = f"关于「{clean_input}」中属于{desc or t}范畴的部分，请进行专业分析和处理。"

        async def _run_one(t: str) -> dict:
            agent = self.dispatcher.get_agent(t)
            display_name = agent.config.display_name if agent else t
            if not agent or not agent.available:
                return {"agent": t, "display_name": display_name, "reply": f"{display_name}暂时不可用", "error": True}
            try:
                reply = await asyncio.wait_for(
                    self.dispatcher.dispatch(t, sub_tasks.get(t, clean_input), status_callback=None),
                    timeout=180,
                )
                if reply is None:
                    reply = f"{display_name}现在有点累了...等会儿再来吧！💤"
                return {"agent": t, "display_name": display_name, "reply": reply}
            except asyncio.TimeoutError:
                return {"agent": t, "display_name": display_name, "reply": f"{display_name}处理超时", "error": True}
            except Exception as e:
                return {"agent": t, "display_name": display_name, "reply": f"处理出错: {e}", "error": True}

        results = await asyncio.gather(*[_run_one(t) for t in targets], return_exceptions=True)

        intermediate = []
        for r in results:
            if isinstance(r, Exception):
                intermediate.append({"agent": "unknown", "display_name": "未知", "reply": f"执行异常: {r}", "error": True})
            elif isinstance(r, dict):
                intermediate.append(r)

        all_replies = "\n\n".join([f"【{r['display_name']}】\n{r['reply']}" for r in intermediate])
        emotion = detect_emotion(clean_input)
        self._last_user_emotion = emotion.get("primary", "")
        asyncio.create_task(self._background_tasks(
            clean_input, all_replies, user_id, source, emotion, [],
            session_id=session_id,
        ))

        if self.router:
            try:
                agent_names = "、".join([r['display_name'] for r in intermediate])
                nahida_prompt = getattr(self.context, "system_prompt", "") or ""
                if not nahida_prompt and hasattr(self.context, "_system_prompt_loader") and self.context._system_prompt_loader:
                    try:
                        nahida_prompt = self.context._system_prompt_loader()
                    except Exception:
                        pass
                if not nahida_prompt:
                    nahida_prompt = "你是纳西妲，须弥的草神。"

                summary = await self.router.route(
                    "chat",
                    [
                        {"role": "system", "content": nahida_prompt},
                        {"role": "user", "content": f"用户请求：{clean_input}"},
                        {"role": "assistant", "content": f"（{agent_names}的并行执行结果如下）\n\n{all_replies}"},
                        {"role": "user", "content": f'以上是{len(intermediate)}位团队成员的并行工作结果，请你整理后向用户做一份完整的汇报：\n1. 先给出一个总体概述（一句话总结全局情况）\n2. 然后按每个团队成员分板块汇报，提取所有具体的事实、数据和关键信息\n3. 最后给出综合评估或建议\n4. 语气温柔但内容必须充实\n5. 如果某个Agent结果明显不完整或报错，如实说明'},
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                )
                if isinstance(summary, str) and summary.strip():
                    all_replies = self._clean_reply(summary)
            except Exception as e:
                logger.warning("agent.parallel_synthesis_failed", error=str(e))

        emotion_label = emotion.get("primary", "")
        clean_reply, sticker_path = self.get_sticker_info(all_replies, self._last_user_emotion)

        audio_path = None
        if self._voice_mode and self.tts.available and len(clean_reply) > 2:
            try:
                audio_path = await self.tts.synthesize_nahida(clean_reply)
            except Exception as e:
                logger.warning("agent.parallel_tts_failed", error=str(e))

        return ProcessResult(reply=clean_reply, emotion=emotion_label, sticker_path=sticker_path, audio_path=audio_path)

    async def delegate_to_klee(self, task: str, factual: bool = False) -> str:
        if factual:
            context = "这是纳西妲委托的查询任务。请直接返回查询结果，不要加任何个人风格、感叹号或角色扮演，只报告事实数据。"
        else:
            context = "纳西妲姐姐委托可莉的任务。纳西妲是须弥的草神，温柔聪慧，可莉叫她'纳西妲姐姐'。用户是纳西妲的爸爸，也是可莉的大哥哥/大姐姐。"
        result = await self.dispatcher.dispatch("keli", task, context=context, status_callback=self._status_callback)
        if result is None:
            return "可莉现在有点累了...等会儿再来找大哥哥玩吧！蹦蹦...💤"
        return result

    async def _rephrase_as_nahida(self, user_input: str, klee_result: str) -> str:
        try:
            prompt = (
                f"用户问：{user_input}\n\n"
                f"查询结果：{klee_result}\n\n"
                f"请用纳西妲的语气（温柔、可爱、偶尔用🌿等emoji）简短转述这个结果，"
                f"1-2句话即可，不要提及可莉或任何查询过程。"
            )
            reply = await self.router.route(
                "chat_flash",
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
            )
            if isinstance(reply, str):
                return reply.strip()
            return reply.choices[0].message.content.strip() if reply.choices[0].message.content else klee_result
        except Exception:
            return klee_result

    async def _notify_status(self, message: str):
        if self._status_callback:
            try:
                await self._status_callback(message)
            except Exception:
                pass

    def _is_manual_target(self, user_input: str, user_id: str) -> bool:
        return any(tag in user_input for tag in ["@可莉", "@银狼", "@昔涟", "@尼可", "@纳西妲"])

    def _is_simple_task(self, user_input: str) -> bool:
        complex_keywords = [
            "搜索", "查一下", "帮我查", "找一下", "搜一下", "查查", "帮我找",
            "搜索一下", "查资料", "搜资料", "写代码", "编程", "调试",
            "研究", "分析", "计算", "执行", "运行", "安装", "部署",
            "翻译", "转换", "生成", "制作", "设计",
            "怎么看", "怎么弄", "如何", "怎么办", "帮我看", "帮我看看",
            "检查", "巡检", "测试", "优化", "修复", "bug", "报错",
        ]
        if any(kw in user_input for kw in complex_keywords):
            return False

        cn_chars = sum(1 for c in user_input if '\u4e00' <= c <= '\u9fff')
        effective_len = cn_chars * 2 + len(user_input) - cn_chars
        if effective_len <= 15:
            return True
        simple_tool_patterns = ["天气", "气温", "时间", "几点", "日期", "星期", "翻译"]
        if effective_len <= 25 and any(kw in user_input for kw in simple_tool_patterns):
            return True
        return False

    async def _nahida_synthesis_chat(self, prompt: str) -> str:
        try:
            result = await self.router.route(
                "chat",
                [
                    {"role": "system", "content": """你是纳西妲，须弥的草神。你的任务是整理团队成员的工作结果，向用户汇报。

重要规则：
1. 必须输出具体的事实信息和关键要点，不要只说空洞的比喻或感想
2. 如果搜索到了新闻/资料，必须列出具体的标题、摘要和关键数据
3. 如果是代码/技术结果，列出核心代码和结论
4. 用简洁清晰的语言组织，可以带一点你的风格但内容必须充实
5. 不要编造信息，只基于提供的内容整理
6. 格式：先一句话总结，然后分点列出具体信息"""},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                temperature=0.5,
            )
            if isinstance(result, str):
                return result.strip()
            return result.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("agent.nahida_synthesis_failed", error=str(e))
            return prompt

    def _parse_chat_target(self, user_input: str, user_id: str) -> list[str]:
        targets = []
        if "@可莉" in user_input:
            targets.append("keli")
        if "@银狼" in user_input:
            targets.append("yinlang")
        if "@昔涟" in user_input:
            targets.append("xilian")
        if "@尼可" in user_input:
            targets.append("nike")
        if "@纳西妲" in user_input:
            targets.append("nahida")

        if targets:
            self._user_chat_target[user_id] = targets[-1]
            return targets

        q = user_input.lower()
        patterns = [
            (r"(?:让|叫|请|麻烦|找|切换到)\s*(?:银狼|yinlang)", "yinlang"),
            (r"(?:让|叫|请|麻烦|找|切换到)\s*(?:可莉|klee|小炸弹)", "keli"),
            (r"(?:让|叫|请|麻烦|找|切换到)\s*(?:昔涟|xilian|记忆)", "xilian"),
            (r"(?:让|叫|请|麻烦|找|切换到)\s*(?:尼可|nike)", "nike"),
            (r"(?:让|叫|请|麻烦|找|切换到)\s*(?:纳西妲|草神|小草神)", "nahida"),
            (r"(?:银狼|yinlang)(?:帮|来|去|看一下|看看|检查|巡检|执行|处理)", "yinlang"),
            (r"(?:可莉|klee|小炸弹)(?:帮|来|去|炸|boom)", "keli"),
            (r"(?:昔涟|xilian)(?:帮|搜|查|找|搜索)", "xilian"),
            (r"(?:尼可|nike)(?:帮|研究|分析|计算)", "nike"),
        ]
        for pattern, target in patterns:
            if re.search(pattern, q):
                self._user_chat_target[user_id] = target
                return [target]

        return [self._user_chat_target.get(user_id, "nahida")]

    def get_chat_target(self, user_id: str) -> str:
        return self._user_chat_target.get(user_id, "nahida")

    def set_chat_target(self, user_id: str, target: str):
        self._user_chat_target[user_id] = target

    async def _nahida_delegate_for_klee(self, question: str) -> str:
        if self._delegate_depth >= 2:
            return "纳西妲姐姐现在也在忙，可莉先自己想想办法吧！"
        self._delegate_depth += 1
        try:
            reply = await self.router.route(
                "chat_flash",
                [{"role": "system", "content": build_system_prompt()},
                 {"role": "user", "content": question}],
                temperature=0.7,
                max_tokens=300,
            )
            if isinstance(reply, str):
                return reply.strip()
            return reply.choices[0].message.content.strip() if reply.choices[0].message.content else "纳西妲姐姐说让她想想..."
        except Exception:
            return "纳西妲姐姐现在有点忙，等会儿再问她吧！"
        finally:
            self._delegate_depth -= 1

    async def get_session(self, user_openid: str) -> dict | None:
        return await self.db.get_active_session(user_openid)

    async def create_session(self, user_openid: str = "") -> str:
        return await self.db.create_session(user_openid)

    async def receive_file(self, attachment) -> dict:
        return await self.file_receiver.receive(attachment)

    def strip_emotion_tag(self, text: str) -> str:
        return self.sticker_manager.strip_emotion_tag(text)

    def set_voice_mode(self, enabled: bool):
        self._voice_mode = enabled

    def get_voice_mode(self) -> bool:
        return self._voice_mode

    async def shutdown(self) -> None:
        if self.router:
            await self.router.flush_costs()
        if self.db:
            await self.db.close()
