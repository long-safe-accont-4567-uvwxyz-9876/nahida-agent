import os
import ctypes
import ctypes.util
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class NPUBuffer:
    ptr: ctypes.c_void_p
    size: int
    dtype: np.dtype
    shape: tuple


class NPUModel:
    def __init__(self, model_path: str, device_id: int = 0):
        self._model_path = model_path
        self._device_id = device_id
        self._handle = None
        self._input_buffers: dict[str, NPUBuffer] = {}
        self._output_buffers: dict[str, NPUBuffer] = {}
        self._input_info: list[dict] = []
        self._output_info: list[dict] = []
        self._available = False

    def _load_library(self):
        lib_names = ["libNBGlinker.so", "libviplite.so", "libovx.so"]
        for name in lib_names:
            lib_path = ctypes.util.find_library(name.replace("lib", "").replace(".so", ""))
            if lib_path:
                return ctypes.CDLL(lib_path)
            for search_dir in ["/usr/lib", "/usr/local/lib", "/opt/vip/lib"]:
                full = os.path.join(search_dir, name)
                if os.path.exists(full):
                    return ctypes.CDLL(full)
        return None

    def load(self) -> bool:
        lib = self._load_library()
        if not lib:
            logger.warning("npu.library_not_found")
            return False

        try:
            if hasattr(lib, "vip_create_kl"):
                lib.vip_create_kl.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
                lib.vip_create_kl.restype = ctypes.c_int

                handle = ctypes.c_void_p()
                model_bytes = self._model_path.encode("utf-8")
                ret = lib.vip_create_kl(model_bytes, self._device_id, ctypes.byref(handle))
                if ret != 0:
                    logger.error("npu.model_load_failed", path=self._model_path, ret=ret)
                    return False

                self._handle = (lib, handle)
                self._available = True
                logger.info("npu.model_loaded", path=self._model_path)
                return True
            else:
                logger.warning("npu.vip_create_kl_not_found")
                return False

        except Exception as e:
            logger.error("npu.load_exception", error=str(e))
            return False

    def allocate_buffers(self, input_shapes: dict[str, tuple], output_shapes: dict[str, tuple],
                         dtype: np.dtype = np.float32):
        if not self._available:
            return

        for name, shape in input_shapes.items():
            size = int(np.prod(shape)) * np.dtype(dtype).itemsize
            buf = np.zeros(shape, dtype=dtype)
            self._input_buffers[name] = NPUBuffer(
                ptr=buf.ctypes.data_as(ctypes.c_void_p),
                size=size,
                dtype=dtype,
                shape=shape,
            )
            self._input_info.append({"name": name, "shape": shape, "dtype": str(dtype)})

        for name, shape in output_shapes.items():
            size = int(np.prod(shape)) * np.dtype(dtype).itemsize
            buf = np.zeros(shape, dtype=dtype)
            self._output_buffers[name] = NPUBuffer(
                ptr=buf.ctypes.data_as(ctypes.c_void_p),
                size=size,
                dtype=dtype,
                shape=shape,
            )
            self._output_info.append({"name": name, "shape": shape, "dtype": str(dtype)})

    def set_input(self, name: str, data: np.ndarray):
        buf = self._input_buffers.get(name)
        if not buf:
            raise ValueError(f"Input buffer '{name}' not found")
        if data.shape != buf.shape:
            data = data.reshape(buf.shape)
        ctypes.memmove(buf.ptr, data.ctypes.data, buf.size)

    def get_output(self, name: str) -> np.ndarray:
        buf = self._output_buffers.get(name)
        if not buf:
            raise ValueError(f"Output buffer '{name}' not found")
        return np.frombuffer((ctypes.c_char * buf.size).from_address(buf.ptr.value), dtype=buf.dtype).reshape(buf.shape)

    def run(self) -> bool:
        if not self._available or not self._handle:
            return False

        try:
            lib, handle = self._handle
            if hasattr(lib, "vip_run_kl"):
                lib.vip_run_kl.argtypes = [ctypes.c_void_p]
                lib.vip_run_kl.restype = ctypes.c_int
                ret = lib.vip_run_kl(handle)
                if ret != 0:
                    logger.error("npu.run_failed", ret=ret)
                    return False
                return True
            return False
        except Exception as e:
            logger.error("npu.run_exception", error=str(e))
            return False

    def release(self):
        if self._handle:
            try:
                lib, handle = self._handle
                if hasattr(lib, "vip_destroy_kl"):
                    lib.vip_destroy_kl.argtypes = [ctypes.c_void_p]
                    lib.vip_destroy_kl.restype = ctypes.c_int
                    lib.vip_destroy_kl(handle)
            except Exception:
                pass
            self._handle = None
        self._input_buffers.clear()
        self._output_buffers.clear()
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def info(self) -> dict:
        return {
            "model_path": self._model_path,
            "device_id": self._device_id,
            "available": self._available,
            "inputs": self._input_info,
            "outputs": self._output_info,
        }


class YOLOv5PostProcessor:
    def __init__(self, input_size: int = 640, conf_threshold: float = 0.25,
                 iou_threshold: float = 0.45, num_classes: int = 80):
        self._input_size = input_size
        self._conf_threshold = conf_threshold
        self._iou_threshold = iou_threshold
        self._num_classes = num_classes
        self._anchors = [
            [(10, 13), (16, 30), (33, 23)],
            [(30, 61), (62, 45), (59, 119)],
            [(116, 90), (156, 198), (373, 326)],
        ]

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    def _decode_predictions(self, predictions: np.ndarray, stride: int, anchors: list) -> np.ndarray:
        batch, grid_h, grid_w, _ = predictions.shape
        num_anchors = len(anchors)
        predictions = predictions.reshape(batch, grid_h, grid_w, num_anchors, 5 + self._num_classes)

        grid_x, grid_y = np.meshgrid(np.arange(grid_w), np.arange(grid_h))
        grid_x = grid_x[..., np.newaxis]
        grid_y = grid_y[..., np.newaxis]

        xy = self._sigmoid(predictions[..., 0:2])
        xy[..., 0] = (xy[..., 0] * 2.0 - 0.5 + grid_x) * stride
        xy[..., 1] = (xy[..., 1] * 2.0 - 0.5 + grid_y) * stride

        wh = np.exp(predictions[..., 2:4])
        for i, (aw, ah) in enumerate(anchors):
            wh[..., i, 0] *= aw
            wh[..., i, 1] *= ah

        obj_conf = self._sigmoid(predictions[..., 4:5])
        class_probs = self._sigmoid(predictions[..., 5:])
        scores = obj_conf * class_probs

        boxes = np.concatenate([xy, wh], axis=-1)
        return boxes.reshape(-1, 4), scores.reshape(-1, self._num_classes)

    def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> list[int]:
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2
        areas = (x2 - x1) * (y2 - y1)

        max_scores = scores.max(axis=1)
        order = max_scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(iou <= self._iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def process(self, outputs: list[np.ndarray], img_w: int, img_h: int) -> list[dict]:
        all_boxes = []
        all_scores = []
        strides = [8, 16, 32]

        for i, (output, stride, anchors) in enumerate(zip(outputs, strides, self._anchors)):
            boxes, scores = self._decode_predictions(output, stride, anchors)
            all_boxes.append(boxes)
            all_scores.append(scores)

        boxes = np.concatenate(all_boxes, axis=0)
        scores = np.concatenate(all_scores, axis=0)

        max_scores = scores.max(axis=1)
        mask = max_scores > self._conf_threshold
        boxes = boxes[mask]
        scores = scores[mask]

        if len(boxes) == 0:
            return []

        scale_x = img_w / self._input_size
        scale_y = img_h / self._input_size
        boxes[:, 0] *= scale_x
        boxes[:, 2] *= scale_x
        boxes[:, 1] *= scale_y
        boxes[:, 3] *= scale_y

        results = []
        for cls_id in range(self._num_classes):
            cls_scores = scores[:, cls_id]
            keep = self._nms(boxes, cls_scores)
            for idx in keep:
                if cls_scores[idx] > self._conf_threshold:
                    cx, cy, w, h = boxes[idx]
                    results.append({
                        "class_id": cls_id,
                        "score": float(cls_scores[idx]),
                        "bbox": [
                            float(cx - w / 2),
                            float(cy - h / 2),
                            float(w),
                            float(h),
                        ],
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results


class NPUInference:
    def __init__(self, model_path: str = "", input_size: int = 640,
                 conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        self._model_path = model_path
        self._input_size = input_size
        self._model: NPUModel | None = None
        self._post_processor = YOLOv5PostProcessor(
            input_size=input_size,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )
        self._available = False
        self._warmup_done = False

    async def init(self) -> bool:
        if not self._model_path or not os.path.exists(self._model_path):
            logger.info("npu_inference.no_model", path=self._model_path)
            return False

        try:
            self._model = NPUModel(self._model_path)
            if not self._model.load():
                logger.warning("npu_inference.model_load_failed")
                return False

            input_shapes = {"images": (1, 3, self._input_size, self._input_size)}
            output_shapes = {
                "output_0": (1, 80, 80, 255),
                "output_1": (1, 40, 40, 255),
                "output_2": (1, 20, 20, 255),
            }
            self._model.allocate_buffers(input_shapes, output_shapes)

            self._available = True
            logger.info("npu_inference.ready", model=self._model_path)
            return True

        except Exception as e:
            logger.error("npu_inference.init_failed", error=str(e))
            return False

    async def warmup(self):
        if not self._available or self._warmup_done:
            return
        try:
            dummy = np.random.randn(1, 3, self._input_size, self._input_size).astype(np.float32)
            self._model.set_input("images", dummy)
            self._model.run()
            self._warmup_done = True
            logger.info("npu_inference.warmup_done")
        except Exception as e:
            logger.warning("npu_inference.warmup_failed", error=str(e))

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.resize(image, (self._input_size, self._input_size))
            image = image.astype(np.float32) / 255.0
            image = np.transpose(image, (2, 0, 1))
            image = np.expand_dims(image, axis=0)
        return np.ascontiguousarray(image)

    async def detect(self, image: np.ndarray) -> list[dict]:
        if not self._available or not self._model:
            return []

        try:
            img_h, img_w = image.shape[:2]
            input_data = self.preprocess(image)

            self._model.set_input("images", input_data)
            if not self._model.run():
                return []

            outputs = []
            for name in ["output_0", "output_1", "output_2"]:
                out = self._model.get_output(name)
                if len(out.shape) == 4:
                    out = np.transpose(out, (0, 2, 3, 1))
                outputs.append(out)

            detections = self._post_processor.process(outputs, img_w, img_h)
            return detections

        except Exception as e:
            logger.error("npu_inference.detect_failed", error=str(e))
            return []

    @property
    def available(self) -> bool:
        return self._available

    async def close(self):
        if self._model:
            self._model.release()
            self._model = None
        self._available = False

    @property
    def info(self) -> dict:
        return {
            "available": self._available,
            "model_path": self._model_path,
            "input_size": self._input_size,
            "model_info": self._model.info if self._model else None,
        }