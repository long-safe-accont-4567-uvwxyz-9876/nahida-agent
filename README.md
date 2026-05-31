# 纳西妲 AI Agent

> 白草净华 — 基于 MiMo 大模型的多 Agent 智能助手

纳西妲 AI Agent 是一个运行在 Orange Pi 4 Pro 上的多 Agent 智能助手系统，以小米 MiMo 大模型为核心，集成了 QQ Bot、CLI 交互界面和 Web UI，支持工具调用、硬件控制、视觉识别、记忆系统等丰富功能。

## 特性

- **多 Agent 协作** — 纳西妲（主 Agent）、可莉、昔涟、银狼、尼可，各具独立人格与能力
- **智能对话** — 基于 MiMo-v2.5 / MiMo-v2.5-Pro，支持深度思考模式
- **工具调用** — 文件操作、代码执行、网络搜索、网页浏览、文档解析（PDF/Word/PPT/Excel）
- **硬件控制** — GPIO 引脚控制、I2C 通信、硬件状态监控、服务管理、网络诊断
- **视觉能力** — USB 摄像头拍照、场景描述、色彩分析、YOLOv10 目标检测
- **记忆系统** — 情景记忆、用户画像、向量检索，跨会话保持上下文
- **知识图谱** — 自动从对话中提取实体与关系，构建结构化知识
- **情绪感知** — 关键词情绪检测，根据用户情绪调整回复风格
- **主动关怀** — Nudge 引擎，定时问候与主动互动
- **笔记本系统** — 笔记与待办事项管理
- **学习系统** — 从交互中归纳经验规则，持续优化行为
- **QQ Bot 集成** — 通过 qq-botpy 接入 QQ，支持私聊
- **TTS 语音** — 回复可附带语音合成

## 系统要求

| 项目       | 要求                              |
| -------- | ------------------------------- |
| Python   | 3.10+                           |
| 操作系统     | Debian 12 / Ubuntu ARM64        |
| 硬件（可选）   | Orange Pi 4 Pro（全志 T507, ARMv8） |
| 摄像头（可选）  | USB 摄像头（如 Q8 HD Webcam）         |
| 外挂存储（可选） |                                 |

## 快速开始

### 1. 克隆仓库

```bash
git clone <repo-url> nahida-agent
cd nahida-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 首次启动

```bash
bash start.sh
```

`start.sh` 会自动启动 QQ Bot 服务并进入 CLI 交互界面。首次运行前请确保已完成配置。

### 4. 手动配置

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的 API 密钥。也可运行交互式配置：

```bash
python setup_wizard.py
```

## 配置说明

所有配置项均在 `.env` 文件中设置。

### 必需配置

| 变量             | 说明                                                        |
| -------------- | --------------------------------------------------------- |
| `MIMO_API_KEY` | MiMo API 密钥，从 [xiaomimimo.com](https://xiaomimimo.com) 获取 |

### 可选配置

| 变量                         | 说明                          |
| -------------------------- | --------------------------- |
| `QQBOT_APP_ID`             | QQ Bot 应用 ID                |
| `QQBOT_APP_SECRET`         | QQ Bot 应用密钥                 |
| `OWNER_IDS`                | 主人 ID（逗号分隔），拥有管理命令权限        |
| `EMBED_API_KEY`            | 向量嵌入 API 密钥（用于记忆检索）         |
| `EMBED_BASE_URL`           | 向量嵌入 API 地址                 |
| `EMBED_MODEL`              | 向量嵌入模型名称                    |
| `IMGBB_API_KEY`            | ImgBB 图片上传 API 密钥           |
| `TAVILY_API_KEY`           | Tavily 搜索 API 密钥            |
| `SILICONFLOW_API_KEY`      | SiliconFlow API 密钥（子 Agent） |
| `OPENROUTER_API_KEY`       | OpenRouter API 密钥（子 Agent）  |
| `KIOXIA_DATA_DIR`          | 外挂存储数据目录路径                  |
| `NUDGE_ENABLED`            | 主动关怀引擎开关（默认 `true`）         |
| `NUDGE_USER_OPENID`        | 主动关怀目标用户 OpenID             |
| `NUDGE_GREETING_THRESHOLD` | 问候触发间隔秒数（默认 `3600`）         |
| `NUDGE_DND_START`          | 免打扰开始时间（小时，默认 `23`）         |
| `NUDGE_DND_END`            | 免打扰结束时间（小时，默认 `7`）          |

## 使用方式

### CLI 模式

```bash
python cli.py
```

进入纳西妲主题的终端交互界面，支持实时对话、斜杠命令和流式输出。

### QQ Bot 模式

```bash
python qq_bot_adapter.py
```

或使用启动脚本：

```bash
bash start_qqbot.sh
```

### Web UI

```bash
streamlit run web/app.py
```

在浏览器中访问 Streamlit 界面。

## 项目结构

```
nahida-agent/
├── agent.py                # 入口（调用 cli.py）
├── agent_core.py           # 核心 Agent 逻辑
├── agent_context.py        # 对话上下文管理
├── agent_dispatcher.py     # 多 Agent 调度器
├── cli.py                  # CLI 交互界面
├── config.py               # 配置加载与系统提示构建
├── model_router.py         # 模型路由与费用追踪
├── tool_registry.py        # 工具注册中心
├── tool_executor.py        # 工具执行器
├── tool_call_handler.py    # 工具调用处理
├── tool_repair.py          # 工具调用修复
├── memory_manager.py       # 记忆管理
├── vector_store.py         # 向量存储（sqlite-vec）
├── knowledge_graph.py      # 知识图谱
├── emotion_simple.py       # 情绪检测
├── nudge_engine.py         # 主动关怀引擎
├── notebook_manager.py     # 笔记本管理
├── learning_manager.py     # 学习系统
├── portrait_manager.py     # 用户画像
├── security.py             # 安全过滤
├── slash_commands.py       # 斜杠命令处理
├── result_wrapper.py       # 结果包装
├── smart_error_handler.py  # 智能错误处理
├── sticker_manager.py      # 表情贴纸管理
├── tts_engine.py           # 语音合成引擎
├── vision_service.py       # 视觉服务
├── klee_agent.py           # 可莉子 Agent
├── task_orchestrator.py    # 任务编排
├── qq_bot_adapter.py       # QQ Bot 适配器
├── database.py             # 数据库管理
├── db_analytics.py         # API 用量分析
├── db_memory.py            # 记忆数据库
├── db_knowledge.py         # 知识数据库
├── db_learning.py          # 学习数据库
├── db_notebook.py          # 笔记本数据库
├── start.sh                # 启动脚本
├── start_qqbot.sh          # QQ Bot 启动脚本
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── *_personality.md        # 各 Agent 人格定义
├── tools/                  # 工具模块
│   ├── file_tools_v2.py    # 文件操作
│   ├── code_tools_v2.py    # 代码执行
│   ├── web_tools_v2.py     # 网络工具
│   ├── web_browse_tools.py # 网页浏览
│   ├── multi_search_tools.py # 多源搜索
│   ├── document_tools.py   # 文档解析
│   ├── hardware_tools.py   # 硬件控制
│   ├── vision_tools.py     # 视觉工具
│   └── system_tools.py     # 系统工具
└── web/
    └── app.py              # Streamlit Web UI
```

## 模型说明

项目使用小米 MiMo 系列大模型，支持两种模式切换：

| 模式          | 模型              | 特点              |
| ----------- | --------------- | --------------- |
| MiMo 模式     | `mimo-v2.5`     | 标准模式，响应快，适合日常对话 |
| MiMo Pro 模式 | `mimo-v2.5-pro` | 深度思考模式，推理能力更强   |

### 定价

| 项目   | MiMo 标准           | MiMo Pro          |
| ---- | ----------------- | ----------------- |
| 输入   | $0.10 / 百万 tokens | $0.20 / 百万 tokens |
| 缓存命中 | $0.01 / 百万 tokens | $0.02 / 百万 tokens |
| 输出   | $0.20 / 百万 tokens | $0.40 / 百万 tokens |

可通过 `/model` 命令切换模式，或设置 `MIMO_MODEL_NAME` / `MIMO_PRO_MODEL_NAME` 环境变量。

## 命令列表

在对话中输入 `/` 开头的斜杠命令可执行特定操作：

### 公共命令

| 命令           | 说明                        |
| ------------ | ------------------------- |
| `/cost [7d]` | 查看 API 消耗（加 `7d` 查看近 7 天） |
| `/status`    | 查看 Agent 状态               |
| `/forget`    | 清除短期对话记忆                  |
| `/learn`     | 查看学习记录                    |
| `/note`      | 查看笔记本                     |
| `/hw`        | 查看硬件状态（CPU/内存/磁盘/负载）      |
| `/cam`       | 拍照并分析摄像头画面                |
| `/cam snap`  | 仅拍照保存                     |
| `/sys`       | 查看系统运行状态                  |
| `/help`      | 显示帮助信息                    |

### 主人专属命令

| 命令                        | 说明           |
| ------------------------- | ------------ |
| `/model [mimo\|mimo-pro]` | 切换模型模式       |
| `/reset`                  | 重置对话上下文      |
| `/voice [on\|off]`        | 切换语音模式       |
| `/agent [名称]`             | 切换对话目标 Agent |

## 许可证

MIT License