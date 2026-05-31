import os
import sys
import inquirer
from loguru import logger


class SetupWizard:

    def __init__(self):
        self._config = {}

    def run(self):
        print("\n🌿 纳西妲 AI Agent 安装向导\n")

        questions = [
            inquirer.Text('api_key', message="请输入 API Key"),
            inquirer.Text('base_url', message="API Base URL", default="https://api.siliconflow.cn/v1"),
            inquirer.Text('model_name', message="模型名称", default="Qwen/Qwen3-8B"),
            inquirer.Text('app_id', message="QQ Bot App ID (可选)"),
            inquirer.Text('app_secret', message="QQ Bot App Secret (可选)"),
        ]

        answers = inquirer.prompt(questions)
        if not answers:
            print("安装已取消")
            return

        env_content = f"""OPENAI_API_KEY={answers['api_key']}
OPENAI_BASE_URL={answers['base_url']}
MODEL_NAME={answers['model_name']}
APP_ID={answers.get('app_id', '')}
APP_SECRET={answers.get('app_secret', '')}
"""
        with open(".env", "w") as f:
            f.write(env_content)

        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        print("\n✅ 安装完成！")
        print("运行 'python agent.py' 启动 CLI 模式")
        print("运行 'python qq_bot_adapter.py' 启动 QQ Bot 模式")
