#!/bin/bash
# 健康检查脚本

echo "🌿 纳西妲 AI Agent 健康检查"
echo "========================"

# 检查 Python 进程
if pgrep -f "python.*agent" > /dev/null; then
    echo "✅ Python Agent 进程运行中"
else
    echo "❌ Python Agent 进程未运行"
fi

# 检查端口
if command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -q ":5000"; then
        echo "✅ Web UI 端口 5000 正常"
    else
        echo "⚠️ Web UI 端口 5000 未监听"
    fi
fi

# 检查磁盘空间
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✅ 磁盘空间充足 ($DISK_USAGE%)"
else
    echo "⚠️ 磁盘空间不足 ($DISK_USAGE%)"
fi

# 检查内存
MEM_USAGE=$(free | awk '/Mem:/ {printf("%.0f", $3/$2 * 100)}')
if [ "$MEM_USAGE" -lt 80 ]; then
    echo "✅ 内存使用正常 ($MEM_USAGE%)"
else
    echo "⚠️ 内存使用较高 ($MEM_USAGE%)"
fi

echo ""
echo "检查完成！"
