import os
import time
from loguru import logger
from openai import AsyncOpenAI


class ModelRouter:

    def __init__(self, config: dict):
        self._config = config
        self._client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )
        self._pro_client = None
        if config.get("api_key_pro") and config.get("base_url_pro"):
            self._pro_client = AsyncOpenAI(
                api_key=config["api_key_pro"],
                base_url=config["base_url_pro"],
            )
        self._model = config.get("model_name", "Qwen/Qwen3-8B")
        self._model_pro = config.get("model_name_pro", "MiMo/MiMo-V2.5-Pro")
        self._embed_model = config.get("embed_model", "BAAI/bge-m3")

    async def route(self, task_type: str, messages: list, **kwargs):
        if task_type == "embed":
            client = self._pro_client or self._client
            model = self._embed_model
            text = kwargs.get("text", "")
            response = await client.embeddings.create(model=model, input=text)
            return response.data[0].embedding

        if task_type == "pro":
            client = self._pro_client or self._client
            model = self._model_pro
        else:
            client = self._client
            model = self._model

        kwargs.pop("text", None)
        kwargs.pop("user_openid", None)
        kwargs.pop("session_id", None)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        return response

    def get_client(self, pro: bool = False) -> AsyncOpenAI:
        if pro and self._pro_client:
            return self._pro_client
        return self._client

    @property
    def model(self) -> str:
        return self._model

    @property
    def model_pro(self) -> str:
        return self._model_pro
