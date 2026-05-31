import os
import sys
import json
import time
import asyncio
import signal
from pathlib import Path
from loguru import logger

from logging_config import setup_logging


def _banner():
    print("""
  \033[32m  ✿  🌿  世  界  的  记  忆  ，  由  我  来  守  护  🌿  ✿

  ✿      _   _____    __  __________  ___      ✿
  ✿     / | / /   |  / / / /  _/ __ \\/   |     ✿
  ✿    /  |/ / /| | / /_/ // // / / / /| |     ✿
  ✿   / /|  / ___ |/ __  // // /_/ / ___ |     ✿
  ✿  /_/ |_/_/  |_/_/ /_/___/_____/_/  |_|     ✿
\033[0m
  \033[36m  🌿  🌿  世  界  的  记  忆  ，  由  我  来  守  护  🌿  🌿\033[0m
""")


def _info_box(router, db, agent_name="nahida"):
    from config import build_system_prompt
    from emoji_config import load_agent_emoji

    model_label = router.get_model_preference_label() if router else "未初始化"
    emoji_cfg = load_agent_emoji(agent_name)
    agent_label = emoji_cfg.get("agent_label", "纳西妲 AI Agent")
    status_emoji = emoji_cfg.get("status_emoji", {})\n    done_emoji = status_emoji.get("done", "🌿")

    stats = {}
    if db:
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            pass
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                try:
                    future = pool.submit(asyncio.run, db.get_stats())
                    stats = future.result(timeout=5)
                except Exception:
                    pass
        else:
            try:
                stats = asyncio.run(db.get_stats())
            except Exception:
                pass

    mem_count = stats.get('memory_count', 0)
    conv_count = stats.get('conversation_count', 0)
    tool_count = stats.get('tool_call_count', 0)
    uptime_s = stats.get('uptime_seconds', 0)

    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    uptime_str = f"{days}天{hours}小时" if days > 0 else f"{hours}小时"

    print(f"  \033[36m+{'='*50}+\033[0m")
    print(f"  \033[36m|\033[0m  {done_emoji}  {agent_label}  ·  {model_label}  \033[36m|\033[0m")
    print(f"  \033[36m+{'-'*50}+\033[0m")
    print(f"  \033[36m|\033[0m  🧠 记忆: {mem_count}条   💬 对话: {conv_count}轮   🔧 工具: {tool_count}次  \033[36m|\033[0m")
    print(f"  \033[36m|\033[0m  ⏱️  运行: {uptime_str}                                 \033[36m|\033[0m")
    print(f"  \033[36m+{'='*50}+\033[0m")


def _get_user_name():
    for name in ("USER", "LOGNAME", "USERNAME"):
        v = os.environ.get(name)
        if v:
            return v
    import getpass
    try:
        return getpass.getuser()
    except Exception:
        return "旅行者"


def _greeting(agent_name: str = "nahida"):
    from emoji_config import load_agent_emoji
    emoji_cfg = load_agent_emoji(agent_name)
    idle_emoji = emoji_cfg.get("status_emoji", {}).get("idle", "🌿")
    name = _get_user_name()
    return f"{idle_emoji} {name}来啦～人家等好久了呢！"


def _farewell(agent_name: str = "nahida"):
    from emoji_config import load_agent_emoji
    emoji_cfg = load_agent_emoji(agent_name)
    farewell_msg = emoji_cfg.get("farewell_msg", "下次再来玩呀～人家会想你的！🌿")
    return farewell_msg


def _should_exit(text: str) -> bool:
    t = text.strip().lower()
    return t in ("exit", "quit", "q", "/exit", "/quit")


async def _process_input(text: str, agent_core, session_id: str, user_openid: str):
    if text.startswith("/"):
        result = await agent_core.handle_command(text, session_id=session_id, user_openid=user_openid)
        if result is not None:
            return result
    return await agent_core.chat(text, session_id=session_id, user_openid=user_openid)


def main():
    setup_logging()

    _banner()

    from agent_core import AgentCore
    from config import load_config

    cfg = load_config()

    if not cfg.get("mimo_api_key"):
        print("\n  ❌ MIMO_API_KEY 未配置！")
        print("  💡 请运行: python3 setup_wizard.py")
        print("     或手动编辑 .env 文件\n")
        sys.exit(1)

    agent = AgentCore(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(agent.initialize())
    except Exception as e:
        logger.error("agent.init_failed", error=str(e))
        print(f"\n  ❌ 初始化失败: {e}")
        print("  💡 请检查 .env 配置和网络连接\n")
        sys.exit(1)

    _banner()
    _info_box(agent.router, agent.db)

    agent_name = cfg.get("agent_name", "nahida")
    session_id = "cli_main"
    user_openid = cfg.get("owner_ids", [""])[0] if cfg.get("owner_ids") else "cli_user"

    print(f"\n  💬 直接输入消息跟纳西妲聊天")
    print(f"  📋 /help 查看所有命令")
    print(f"  🚪 exit 或 Ctrl+C 退出\n")
    print(f"  {_greeting(agent_name)}\n")

    def _signal_handler(sig, frame):
        print(f"\n  {_farewell(agent_name)}\n")
        loop.run_until_complete(agent.shutdown())
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    while True:
        try:
            text = input("\033[32m  你 > \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {_farewell(agent_name)}\n")
            break

        if not text:
            continue

        if _should_exit(text):
            print(f"\n  {_farewell(agent_name)}\n")
            break

        try:
            reply = loop.run_until_complete(
                _process_input(text, agent, session_id, user_openid)
            )
            if reply:
                print(f"\n  \033[36m🌿 纳西妲 > \033[0m{reply}\n")
        except KeyboardInterrupt:
            print(f"\n  {_farewell(agent_name)}\n")
            break
        except Exception as e:
            logger.error("cli.process_error", error=str(e))
            print(f"\n  ❌ 出错了: {e}\n")

    try:
        loop.run_until_complete(agent.shutdown())
    except Exception:
        pass
    loop.close()


if __name__ == "__main__":
    main()
