"""共享测试配置和 fixtures"""
import os
import sys
from pathlib import Path

# 统一设置项目路径
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试环境默认启用开发板模式（安全威胁 warn 不 block）
os.environ.setdefault("AGENT_DEV_MODE", "1")
