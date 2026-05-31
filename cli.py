import sys
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging
setup_logging()

from config import load_config
from agent_core import AgentCore
from slash_commands import SlashCommandHandler


async def main():
    config = load_config()
    agent = AgentCore(config)
    await agent.init()

    cmd_handler = SlashCommandHandler(agent)

    print("\n🌿 纳西妲 AI Agent v2.0 - CLI模式")
    print("输入消息开始对话，输入 /help 查看命令\n")

    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                result = await cmd_handler.handle(user_input)
                print(f"\n{result}\n")
                continue

            async def status_cb(msg: str):
                print(f"  {msg}")

            reply = await agent.process(
                user_input,
                user_id="cli_user",
                status_callback=status_cb,
            )
            print(f"\n🌿 纳西妲：{reply}\n")

        except KeyboardInterrupt:
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\n出错了: {e}\n")

    await agent.close()
    print("\n再见，旅行者！🌿\n")


if __name__ == "__main__":
    asyncio.run(main())
