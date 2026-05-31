import os
import asyncio
import speech_recognition as sr
from loguru import logger


class VisionService:

    def __init__(self, config: dict):
        self._config = config
        self._camera_id = 0

    async def capture_image(self, save_path: str = "data/camera.jpg") -> str:
        try:
            import cv2
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            cap = cv2.VideoCapture(self._camera_id)
            if not cap.isOpened():
                raise Exception("无法打开摄像头")
            ret, frame = cap.read()
            cap.release()
            if not ret:
                raise Exception("无法捕获图像")
            cv2.imwrite(save_path, frame)
            return save_path
        except ImportError:
            raise Exception("需要安装 opencv-python")

    async def analyze_image(self, image_path: str, question: str = "描述这张图片") -> str:
        import base64
        from openai import AsyncOpenAI
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        suffix = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix, "image/jpeg")
        client = AsyncOpenAI(
            api_key=self._config["api_key"],
            base_url=self._config["base_url"],
        )
        response = await client.chat.completions.create(
            model=self._config.get("model_name", "Qwen/Qwen3-8B"),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                ],
            }],
            max_tokens=1000,
        )
        return response.choices[0].message.content

    async def listen_audio(self, duration: int = 5) -> str:
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                logger.info("vision_service.listening", duration=duration)
                audio = recognizer.listen(source, timeout=duration)
            text = recognizer.recognize_google(audio, language="zh-CN")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise Exception(f"语音识别服务错误：{e}")
        except Exception as e:
            raise Exception(f"语音捕获失败：{e}")
