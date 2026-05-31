import os
import json
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from config import load_config
from agent_core import AgentCore

app = Flask(__name__)
CORS(app)

config = load_config()
agent = None


async def init_agent():
    global agent
    agent = AgentCore(config)
    await agent.init()


@app.route("/")
def index():
    return "<h1>纳西妲 AI Agent Web UI</h1><p>API endpoint: POST /api/chat</p>"


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    user_id = data.get("user_id", "web_user")
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    import asyncio
    loop = asyncio.new_event_loop()
    try:
        reply = loop.run_until_complete(agent.process(message, user_id=user_id))
        return jsonify({"reply": reply})
    finally:
        loop.close()


@app.route("/api/status")
def status():
    return jsonify({
        "status": "running",
        "model": config.get("model_name"),
    })


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_agent())
    port = config.get("web_port", 5000)
    host = config.get("web_host", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
