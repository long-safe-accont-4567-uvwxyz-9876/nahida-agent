import os
import sys
import asyncio
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging
setup_logging()

from config import load_config
from agent_core import AgentCore


async def main():
    config = load_config()
    agent = AgentCore(config)
    await agent.init()
    
    logger.info("agent.started", model=config.get("model_name"))
    print("\n🌿 纳西妲 AI Agent v2.0")
    print("输入 /help 查看命令列表，输入 /exit 退出\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue
            
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd == "/exit":
                    break
                elif cmd == "/help":
                    print("\n可用命令:")
                    print("  /help    - 显示帮助")
                    print("  /clear   - 清除对话历史")
                    print("  /memory  - 查看记忆")
                    print("  /tools   - 查看可用工具")
                    print("  /status  - 查看系统状态")
                    print("  /exit    - 退出\n")
                    continue
                elif cmd == "/clear":
                    agent.context.clear()
                    print("对话历史已清除")
                    continue
                elif cmd == "/memory":
                    memories = await agent.memory.get_recent(limit=10)
                    if memories:
                        for m in memories:
                            print(f"  [{m['created_at']}] {m['content'][:80]}")
                    else:
                        print("暂无记忆")
                    continue
                elif cmd == "/tools":
                    from tool_registry import list_tools
                    tools = list_tools()
                    for t in tools:
                        print(f"  {t['name']}: {t['description']}")
                    continue
                elif cmd == "/status":
                    print(f"模型: {config.get('model_name')}")
                    print(f"会话: {agent.context.session_id}")
                    continue
            
            reply = await agent.process(user_input, user_id="cli_user")
            print(f"\n🌿 纳西妲：{reply}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("agent.error", error=str(e))
            print(f"\n出错了: {e}\n")
    
    await agent.close()
    print("\n再见，旅行者！🌿\n")


if __name__ == "__main__":
    asyncio.run(main())
