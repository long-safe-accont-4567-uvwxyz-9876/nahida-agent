#!/bin/bash
# 纳西妲 AI Agent 启动脚本

echo "🌿 启动纳西妲 AI Agent..."

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
if [ -f "requirements.txt" ]; then
    echo "📦 检查依赖..."
    pip3 install -r requirements.txt -q
fi

# 创建数据目录
mkdir -p data logs

# 启动 CLI 模式
if [ "$1" == "cli" ] || [ -z "$1" ]; then
    echo "🌿 启动 CLI 模式..."
    python3 agent.py
elif [ "$1" == "bot" ]; then
    echo "🌿 启动 QQ Bot 模式..."
    python3 qq_bot_adapter.py
elif [ "$1" == "web" ]; then
    echo "🌿 启动 Web UI 模式..."
    python3 web/app.py
else
    echo "用法: bash start.sh [cli|bot|web]"
fi
