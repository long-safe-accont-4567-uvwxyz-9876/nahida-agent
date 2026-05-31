import os
import asyncio
from loguru import logger


class TTSEngine:

    def __init__(self, config: dict):
        self._config = config
        self._engine = "edge"
        self._voice = "zh-CN-XiaoyiNeural"

    async def speak(self, text: str, save_path: str = "data/tts_output.mp3") -> str:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        if self._engine == "edge":
            return await self._speak_edge(text, save_path)
        elif self._engine == "pyttsx3":
            return await self._speak_pyttsx3(text, save_path)
        else:
            raise Exception(f"不支持的TTS引擎：{self._engine}")

    async def _speak_edge(self, text: str, save_path: str) -> str:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(save_path)
            return save_path
        except ImportError:
            raise Exception("需要安装 edge-tts：pip install edge-tts")

    async def _speak_pyttsx3(self, text: str, save_path: str) -> str:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text, save_path)
            engine.runAndWait()
            return save_path
        except ImportError:
            raise Exception("需要安装 pyttsx3：pip install pyttsx3")

    def set_voice(self, voice: str):
        self._voice = voice

    def set_engine(self, engine: str):
        self._engine = engine
