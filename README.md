# AI Agent

全能型 AI Agent，运行在 Orange Pi 上。

## 功能

- 📁 文件操作：列出、读取、写入、搜索文件
- 💻 代码执行：运行 Python 代码
- 🌐 网络搜索：搜索互联网获取信息
- 🖥️ 系统操作：执行 Shell 命令

## 安装

```bash
cd ~/ai-agent
pip install -r requirements.txt
```

## 运行

命令行模式:
```bash
python agent.py
```

Web UI 模式:
```bash
streamlit run web/app.py
```

## 配置

编辑 `.env` 文件配置 API 密钥。