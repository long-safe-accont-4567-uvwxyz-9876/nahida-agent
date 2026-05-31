import os
import sys
import ssl
import asyncio
import base64
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

_original_create_default_context = ssl.create_default_context

def _patched_create_default_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

ssl.create_default_context = _patched_create_default_context

from logging_config import setup_logging
setup_logging()

from loguru import logger

import botpy
from botpy.gateway import BotWebSocket
from botpy.message import C2CMessage, GroupMessage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_core import AgentCore, ProcessResult
from config import AGENT_CONFIG
from nudge_engine import NudgeEngine

_original_is_system_event = BotWebSocket._is_system_event

async def _patched_is_system_event(self, message_event, ws):
    event_op = message_event.get("op")
    if event_op == BotWebSocket.WS_HEARTBEAT_ACK:
        self._last_heartbeat_ack = asyncio.get_event_loop().time()
    return await _original_is_system_event(self, message_event, ws)

BotWebSocket._is_system_event = _patched_is_system_event

_original_send_heart = BotWebSocket._send_heart

async def _patched_send_heart(self, interval):
    _log = __import__("botpy.logging", fromlist=["get_logger"]).get_logger()
    _log.info("[botpy] \u5fc3\u8df3\u7ef4\u6301\u542f\u52a8\uff08\u5e26\u8d85\u65f6\u68c0\u6d4b\uff09...")
    self._last_heartbeat_ack = asyncio.get_event_loop().time()
    missed_acks = 0
    while True:
        if self._conn is None:
            _log.debug("[botpy] \u8fde\u63a5\u5df2\u5173\u95ed!")
            return
        if self._conn.closed:
            _log.debug("[botpy] ws\u8fde\u63a5\u5df2\u5173\u95ed, \u5fc3\u8df3\u68c0\u6d4b\u505c\u6b62")
            return

        now = asyncio.get_event_loop().time()
        if now - self._last_heartbeat_ack > interval * 2.5:
            missed_acks += 1
            _log.warning(f"[botpy] \u5fc3\u8df3ACK\u8d85\u65f6 ({missed_acks}\u6b21), \u4e0a\u6b21ACK: {int(now - self._last_heartbeat_ack)}\u79d2\u524d")
            if missed_acks >= 2:
                _log.warning("[botpy] \u5fc3\u8df3ACK\u8fde\u7eed\u8d85\u65f6\uff0c\u5f3a\u5236\u65ad\u5f00\u91cd\u8fde!")
                await self._conn.close()
                return
        else:
            missed_acks = 0

        payload = {
            "op": self.WS_HEARTBEAT,
            "d": self._session["last_seq"],
        }
        await self.send_msg(__import__("json").dumps(payload))
        await asyncio.sleep(interval)

BotWebSocket._send_heart = _patched_send_heart

APP_ID = os.getenv("QQBOT_APP_ID")
APP_SECRET = os.getenv("QQBOT_APP_SECRET")

_qq_cfg = AGENT_CONFIG.get("qq_bot", {})
MAX_REPLY_LEN = _qq_cfg.get("max_reply_length", 8000)

_msg_seq_counter = int(time.time() * 1000) % (10 ** 8)

def _next_msg_seq() -> int:
    global _msg_seq_counter
    _msg_seq_counter += 1
    return _msg_seq_counter


class AIQQBot(botpy.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = AgentCore()
        self.nudge_engine = None
        self._processed_msg_ids = set()
        self._MAX_MSG_IDS = 100

    def _is_duplicate_msg(self, msg_id: str) -> bool:
        if msg_id in self._processed_msg_ids:
            return True
        self._processed_msg_ids.add(msg_id)
        if len(self._processed_msg_ids) > self._MAX_MSG_IDS:
            excess = len(self._processed_msg_ids) - self._MAX_MSG_IDS
            for _ in range(excess):
                self._processed_msg_ids.pop()
        return False

    async def on_ready(self):
        logger.info("qq_bot.connected", app_id=APP_ID)
        await self.agent.init()

        nudge_enabled = os.getenv("NUDGE_ENABLED", "false").lower() == "true"
        if nudge_enabled:
            user_openid = os.getenv("NUDGE_USER_OPENID", "")
            if user_openid:
                try:
                    self.nudge_engine = NudgeEngine(
                        db=self.agent.db,
                        analytics=self.agent.db.analytics,
                        router=self.agent.router,
                        api=self.api,
                        user_openid=user_openid,
                        greeting_threshold=int(os.getenv("NUDGE_GREETING_THRESHOLD", "3600")),
                        dnd_start=int(os.getenv("NUDGE_DND_START", "23")),
                        dnd_end=int(os.getenv("NUDGE_DND_END", "8")),
                        portrait_manager=self.agent.portrait_manager,
                    )
                    await self.nudge_engine.start()
                except Exception as e:
                    logger.warning("nudge.init_failed", error=str(e))

        logger.info("qq_bot.agent_initialized")

    async def on_error(self, error):
        logger.error("qq_bot.ws_error", error=str(error)[:200])

    async def on_close(self, close_status_code, close_msg):
        logger.warning("qq_bot.ws_closed", code=close_status_code, msg=str(close_msg)[:100])

    async def on_c2c_message_create(self, message: C2CMessage):
        content = message.content.strip()

        attachment_info = ""
        if hasattr(message, 'attachments') and message.attachments:
            parts = []
            for att in message.attachments:
                ct = getattr(att, 'content_type', '') or ''
                fn = getattr(att, 'filename', '') or ''
                result = await self.agent.receive_file(att)
                if result["status"] == "ok":
                    if result.get("text_preview"):
                        parts.append(f"[\u6587\u4ef6: {fn}]\n\u5185\u5bb9\u9884\u89c8:\n{result['text_preview'][:500]}")
                    else:
                        parts.append(f"[\u6587\u4ef6: {fn}\uff0c\u5df2\u4fdd\u5b58\u5230 {result['save_path']}]")
                else:
                    if ct.startswith("image/"):
                        parts.append(f"[\u56fe\u7247: {fn or 'image'}]")
                    elif ct.startswith("video/"):
                        parts.append(f"[\u89c6\u9891: {fn or 'video'}]")
                    else:
                        parts.append(f"[\u9644\u4ef6: {fn or 'unknown'}]")
            attachment_info = " ".join(str(p) for p in parts)

        if not content and not attachment_info:
            return

        user_input = f"{content} {attachment_info}".strip() if content else attachment_info

        user_openid = getattr(message.author, 'user_openid', '') if hasattr(message, 'author') else ''
        user_id = f"qq_{user_openid}" if user_openid else "qq_unknown"
        logger.info("qq_bot.c2c_message", user_id=user_id, openid=user_openid, content=user_input[:80])

        if self.nudge_engine:
            self.nudge_engine.poke()

        session_id = ""
        try:
            session = await self.agent.get_session(user_openid)
            if session:
                session_id = session["id"]
            else:
                session_id = await self.agent.create_session(user_openid)
        except Exception:
            pass

        msg_id = getattr(message, 'id', '') or getattr(message, 'message_id', '')
        if msg_id and self._is_duplicate_msg(msg_id):
            return

        try:
            await message.reply(content="\u7eb3\u897f\u59b2\u6536\u5230\u5566\uff0c\u6b63\u5728\u60f3\uff5e\ud83c\udf3f", msg_seq=_next_msg_seq())

            async def status_notify(msg: str):
                await message.reply(content=msg, msg_seq=_next_msg_seq())

            result = await self.agent.process(user_input, user_id=user_id, source="qq_c2c",
                                              user_openid=user_openid, session_id=session_id,
                                              status_callback=status_notify)
            if result.reply:
                await self._send_reply_with_sticker(message, result)
        except Exception as e:
            logger.error(f"qq_bot.c2c_error: {e}")
            try:
                await message.reply(content="\u55ef\u2026\u2026\u51fa\u4e86\u70b9\u5c0f\u95ee\u9898\uff0c\u7b49\u4f1a\u513f\u518d\u804a\u597d\u4e0d\u597d\uff1f", msg_seq=_next_msg_seq())
            except Exception:
                pass

    async def on_group_at_message_create(self, message: GroupMessage):
        content = message.content.strip()

        attachment_info = ""
        if hasattr(message, 'attachments') and message.attachments:
            parts = []
            for att in message.attachments:
                ct = getattr(att, 'content_type', '') or ''
                fn = getattr(att, 'filename', '') or ''
                result = await self.agent.receive_file(att)
                if result["status"] == "ok":
                    if result.get("text_preview"):
                        parts.append(f"[\u6587\u4ef6: {fn}]\n\u5185\u5bb9\u9884\u89c8:\n{result['text_preview'][:500]}")
                    else:
                        parts.append(f"[\u6587\u4ef6: {fn}\uff0c\u5df2\u4fdd\u5b58\u5230 {result['save_path']}]")
                else:
                    if ct.startswith("image/"):
                        parts.append(f"[\u56fe\u7247: {fn or 'image'}]")
                    elif ct.startswith("video/"):
                        parts.append(f"[\u89c6\u9891: {fn or 'video'}]")
                    else:
                        parts.append(f"[\u9644\u4ef6: {fn or 'unknown'}]")
            attachment_info = " ".join(str(p) for p in parts)

        if not content and not attachment_info:
            return

        user_input = f"{content} {attachment_info}".strip() if content else attachment_info

        member_openid = getattr(message.author, 'member_openid', '') if hasattr(message, 'author') else ''
        user_id = f"qq_{member_openid}" if member_openid else "qq_unknown"
        logger.info("qq_bot.group_message", user_id=user_id, openid=member_openid, content=user_input[:80])

        if self.nudge_engine:
            self.nudge_engine.poke()

        msg_id = getattr(message, 'id', '') or getattr(message, 'message_id', '')
        if msg_id and self._is_duplicate_msg(msg_id):
            return

        try:
            await message.reply(content="\u7eb3\u897f\u59b2\u6536\u5230\u5566\uff0c\u6b63\u5728\u60f3\uff5e\ud83c\udf3f", msg_seq=_next_msg_seq())

            async def status_notify(msg: str):
                await message.reply(content=msg, msg_seq=_next_msg_seq())

            result = await self.agent.process(user_input, user_id=user_id, source="qq_group",
                                              user_openid=member_openid,
                                              status_callback=status_notify)
            if result.reply:
                await self._send_reply_with_sticker(message, result)
        except Exception as e:
            logger.error(f"qq_bot.group_error: {e}")
            try:
                await message.reply(content="\u55ef\u2026\u2026\u51fa\u4e86\u70b9\u5c0f\u95ee\u9898\uff0c\u7b49\u4f1a\u513f\u518d\u804a\u597d\u4e0d\u597d\uff1f", msg_seq=_next_msg_seq())
            except Exception:
                pass

    async def _send_reply_with_media(self, message, reply: str,
                                      image_path: Path | None = None,
                                      image_url: str | None = None):
        if not image_path and not image_url:
            await message.reply(content=reply, msg_seq=_next_msg_seq())
            return

        try:
            if isinstance(message, C2CMessage):
                openid = message.author.user_openid
                if image_path:
                    file_info = await self._upload_c2c_base64(openid, image_path)
                else:
                    media = await self.api.post_c2c_file(
                        openid=openid, file_type=1, url=image_url
                    )
                    file_info = media.file_info
                await self.api.post_c2c_message(
                    openid=openid, msg_id=message.id,
                    msg_type=7, content=reply,
                    media={"file_info": file_info}, msg_seq=_next_msg_seq()
                )
            elif isinstance(message, GroupMessage):
                group_openid = message.group_openid
                if image_path:
                    file_info = await self._upload_group_base64(group_openid, image_path)
                else:
                    media = await self.api.post_group_file(
                        group_openid=group_openid, file_type=1, url=image_url
                    )
                    file_info = media.file_info
                await self.api.post_group_message(
                    group_openid=group_openid, msg_id=message.id,
                    msg_type=7, content=reply,
                    media={"file_info": file_info}, msg_seq=_next_msg_seq()
                )
            else:
                await message.reply(content=reply, msg_seq=_next_msg_seq())
        except Exception as e:
            logger.warning("qq_bot.media_send_failed", error=str(e))
            await message.reply(content=reply, msg_seq=_next_msg_seq())

    async def _upload_c2c_base64(self, openid: str, image_path: Path, file_type: int = 1) -> str:
        from botpy.http import Route

        def _read():
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        file_data = await asyncio.to_thread(_read)
        payload = {
            "openid": openid,
            "file_type": file_type,
            "file_data": file_data,
            "srv_send_msg": False,
        }
        route = Route("POST", "/v2/users/{openid}/files", openid=openid)
        result = await self.api._http.request(route, json=payload)
        if isinstance(result, dict):
            return result.get("file_info", "")
        return result.file_info

    async def _upload_group_base64(self, group_openid: str, image_path: Path, file_type: int = 1) -> str:
        from botpy.http import Route

        def _read():
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        file_data = await asyncio.to_thread(_read)
        payload = {
            "group_openid": group_openid,
            "file_type": file_type,
            "file_data": file_data,
            "srv_send_msg": False,
        }
        route = Route("POST", "/v2/groups/{group_openid}/files", group_openid=group_openid)
        result = await self.api._http.request(route, json=payload)
        if isinstance(result, dict):
            return result.get("file_info", "")
        return result.file_info

    async def _send_reply_with_sticker(self, message, result: ProcessResult):
        from text_utils import smart_truncate, split_long_reply

        reply = result.reply
        clean_reply = self.agent.strip_emotion_tag(reply)

        parts = split_long_reply(clean_reply, MAX_REPLY_LEN)

        if len(parts) == 1:
            final_text = parts[0]
        else:
            for part in parts[:-1]:
                try:
                    await message.reply(content=part, msg_seq=_next_msg_seq())
                except Exception:
                    pass
            final_text = parts[-1]

        if result.sticker_path:
            try:
                await self._send_reply_with_media(message, final_text, image_path=result.sticker_path)
            except Exception as e:
                logger.warning("qq_bot.sticker_send_failed", error=str(e))
                await message.reply(content=final_text, msg_seq=_next_msg_seq())
        else:
            await message.reply(content=final_text, msg_seq=_next_msg_seq())

        if result.audio_path and result.audio_path.exists():
            try:
                await self._send_audio(message, result.audio_path)
            except Exception as e:
                logger.warning("qq_bot.audio_send_failed", error=str(e))

    async def _send_audio(self, message, audio_path: Path):
        if isinstance(message, C2CMessage):
            openid = message.author.user_openid
            file_info = await self._upload_c2c_base64(openid, audio_path, file_type=3)
            await self.api.post_c2c_message(
                openid=openid, msg_id=message.id,
                msg_type=7, content="",
                media={"file_info": file_info}, msg_seq=_next_msg_seq()
            )
        elif isinstance(message, GroupMessage):
            group_openid = message.group_openid
            file_info = await self._upload_group_base64(group_openid, audio_path, file_type=3)
            await self.api.post_group_message(
                group_openid=group_openid, msg_id=message.id,
                msg_type=7, content="",
                media={"file_info": file_info}, msg_seq=_next_msg_seq()
            )


if __name__ == "__main__":
    if not APP_ID or APP_ID == "your_app_id_here":
        print("=" * 55)
        print("  \u8bf7\u5148\u914d\u7f6e QQ Bot AppID \u548c AppSecret")
        print("")
        print("  \u6b65\u9aa4:")
        print("  1. \u6d4f\u89c8\u5668\u6253\u5f00: https://q.qq.com")
        print("  2. \u7528\u624b\u673a QQ \u626b\u7801\u767b\u5f55")
        print("  3. \u70b9\u51fb\u300c\u521b\u5efa\u673a\u5668\u4eba\u300d")
        print("  4. \u590d\u5236 AppID \u548c AppSecret")
        print("  5. \u586b\u5165 .env \u6587\u4ef6")
        print("=" * 55)
        sys.exit(1)

    print("=" * 50)
    print("\u7eb3\u897f\u59b2\u7684 QQ Bot \u542f\u52a8\u4e2d...")
    print("  \u79c1\u804a: \u5168\u81ea\u52a8\u56de\u590d")
    print("  \u7fa4\u804a: @\u673a\u5668\u4eba \u89e6\u53d1")
    print("=" * 50)

    intents = botpy.Intents(public_messages=True)
    is_sandbox = _qq_cfg.get("is_sandbox", False)
    client = AIQQBot(intents=intents, is_sandbox=is_sandbox)

    client.run(appid=APP_ID, secret=APP_SECRET)
