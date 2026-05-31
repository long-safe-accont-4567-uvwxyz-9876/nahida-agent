import os
import onnxruntime as ort
from loguru import logger


class NPUInference:

    def __init__(self, model_path: str = ""):
        self._model_path = model_path
        self._session = None
        self._available = False

    async def init(self):
        if not self._model_path or not os.path.exists(self._model_path):
            logger.info("npu_inference.no_model", path=self._model_path)
            return

        try:
            providers = ['CPUExecutionProvider']
            if 'NPUExecutionProvider' in ort.get_available_providers():
                providers.insert(0, 'NPUExecutionProvider')

            self._session = ort.InferenceSession(self._model_path, providers=providers)
            self._available = True
            logger.info("npu_inference.ready", providers=providers)
        except Exception as e:
            logger.warning("npu_inference.init_failed", error=str(e))

    @property
    def available(self) -> bool:
        return self._available

    async def infer(self, inputs: dict) -> dict:
        if not self._available or not self._session:
            return {"error": "NPU not available"}
        try:
            results = self._session.run(None, inputs)
            return {"outputs": [r.tolist() for r in results]}
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        self._session = None
        self._available = False
