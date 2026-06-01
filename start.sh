#!/bin/bash
cd /home/orangepi/ai-agent

echo "正在启动纳西妲 Agent 服务..."
sudo systemctl start qq-agent
sleep 2

STATUS=$(sudo systemctl is-active qq-agent)
if [ "$STATUS" = "active" ]; then
    echo "QQ Bot 服务已启动 ✓"
else
    echo "QQ Bot 服务启动失败，请检查: sudo journalctl -u qq-agent"
fi

echo ""
echo "启动 CLI 交互界面..."
echo ""
exec /home/orangepi/miniconda3/bin/python cli.py
