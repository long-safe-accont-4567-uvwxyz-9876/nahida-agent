#!/bin/bash
# QQ Bot 启动脚本

echo "🌿 启动纳西妲 QQ Bot..."

# 检查环境变量
if [ -z "$APP_ID" ] || [ -z "$APP_SECRET" ]; then
    if [ -f ".env" ]; then
        source .env
    fi
fi

if [ -z "$APP_ID" ] || [ -z "$APP_SECRET" ]; then
    echo "❌ 请配置 APP_ID 和 APP_SECRET"
    echo "可以复制 .env.example 为 .env 并填入配置"
    exit 1
fi

# 创建数据目录
mkdir -p data logs

# 启动
python3 qq_bot_adapter.py
