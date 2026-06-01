#!/usr/bin/env python3
import numpy as np
import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from npu_inference import NPUModel, INPUT_SIZE, _sigmoid

MODEL_PATH = '/home/orangepi/ai-agent/models/yolov5.nb'
TEST_IMAGE = '/opt/yolov5/input_data/dog_640_640.jpg'

YOLOV5_ANCHORS = [
    [(10, 13), (16, 30), (33, 23)],
    [(30, 61), (62, 45), (59, 119)],
    [(116, 90), (156, 198), (373, 326)],
]

COCO_STANDARD = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


def _iou(a, b):
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0


def _nms(dets, threshold=0.45, max_det=100):
    if not dets:
        return []
    dets.sort(key=lambda d: d[1], reverse=True)
    dets = dets[:max_det * 3]
    keep = []
    while dets:
        best = dets.pop(0)
        keep.append(best)
        if len(keep) >= max_det:
            break
        dets = [d for d in dets if _iou(best[0], d[0]) < threshold]
    return keep


def decode_scale(data, stride, anchors, layout="85,g,g,3"):
    grid_h = INPUT_SIZE // stride
    grid_w = INPUT_SIZE // stride
    total = 85 * grid_h * grid_w * 3
    if data.size < total:
        return []

    dets = []
    anchor_list = anchors
    gx, gy = np.meshgrid(np.arange(grid_w), np.arange(grid_h))

    for ai in range(3):
        aw, ah = anchor_list[ai]

        if layout == "85,g,g,3":
            out = data.reshape(85, grid_h, grid_w, 3)
            obj = _sigmoid(out[0, :, :, ai])
            tx = out[1, :, :, ai]
            ty = out[2, :, :, ai]
            tw = out[3, :, :, ai]
            th = out[4, :, :, ai]
            cls = _sigmoid(out[5:85, :, :, ai].transpose(1, 2, 0))
        elif layout == "3,g,g,85":
            out = data.reshape(3, grid_h, grid_w, 85)
            obj = _sigmoid(out[ai, :, :, 0])
            tx = out[ai, :, :, 1]
            ty = out[ai, :, :, 2]
            tw = out[ai, :, :, 3]
            th = out[ai, :, :, 4]
            cls = _sigmoid(out[ai, :, :, 5:85])
        elif layout == "g,g,3,85":
            out = data.reshape(grid_h, grid_w, 3, 85)
            obj = _sigmoid(out[:, :, ai, 0])
            tx = out[:, :, ai, 1]
            ty = out[:, :, ai, 2]
            tw = out[:, :, ai, 3]
            th = out[:, :, ai, 4]
            cls = _sigmoid(out[:, :, ai, 5:85])
        elif layout == "g,g,85,3":
            out = data.reshape(grid_h, grid_w, 85, 3)
            obj = _sigmoid(out[:, :, 0, ai])
            tx = out[:, :, 1, ai]
            ty = out[:, :, 2, ai]
            tw = out[:, :, 3, ai]
            th = out[:, :, 4, ai]
            cls = _sigmoid(out[:, :, 5:85, ai])
        elif layout == "3,85,g,g":
            out = data.reshape(3, 85, grid_h, grid_w)
            obj = _sigmoid(out[ai, 0, :, :])
            tx = out[ai, 1, :, :]
            ty = out[ai, 2, :, :]
            tw = out[ai, 3, :, :]
            th = out[ai, 4, :, :]
            cls = _sigmoid(out[ai, 5:85, :, :].transpose(1, 2, 0))
        elif layout == "85,3,g,g":
            out = data.reshape(85, 3, grid_h, grid_w)
            obj = _sigmoid(out[0, ai, :, :])
            tx = out[1, ai, :, :]
            ty = out[2, ai, :, :]
            tw = out[3, ai, :, :]
            th = out[4, ai, :, :]
            cls = _sigmoid(out[5:85, ai, :, :].transpose(1, 2, 0))
        else:
            continue

        cx = (_sigmoid(tx) * 2 - 0.5 + gx) * stride
        cy = (_sigmoid(ty) * 2 - 0.5 + gy) * stride
        w = (_sigmoid(tw) * 2) ** 2 * aw
        h = (_sigmoid(th) * 2) ** 2 * ah
        max_cls = np.max(cls, axis=-1)
        conf = obj * max_cls
        mask = conf > 0.15
        indices = np.argwhere(mask)
        for idx in indices:
            yi, xi = int(idx[0]), int(idx[1])
            bw = float(w[yi, xi])
            bh = float(h[yi, xi])
            if bw < 1 or bh < 1:
                continue
            bcx = float(cx[yi, xi])
            bcy = float(cy[yi, xi])
            bconf = float(conf[yi, xi])
            cid = int(np.argmax(cls[yi, xi]))
            dets.append(([bcx - bw/2, bcy - bh/2, bcx + bw/2, bcy + bh/2], bconf, cid))

    return dets


def main():
    model = NPUModel(MODEL_PATH)
    if not model.loaded:
        print('Model not loaded')
        return

    img = cv2.imread(TEST_IMAGE)
    if img is None:
        print(f'Cannot read {TEST_IMAGE}')
        return

    img_resized = cv2.resize(img, (INPUT_SIZE, INPUT_SIZE))
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    input_bytes = img_rgb.astype(np.uint8).tobytes()

    outputs = model.run(input_bytes)
    print(f'Number of outputs: {len(outputs)}')
    for i, out in enumerate(outputs):
        arr = np.frombuffer(out, dtype=np.float32)
        print(f'Output {i}: {len(out)} bytes, {arr.size} floats')

    layouts = ["85,g,g,3", "3,g,g,85", "g,g,3,85", "g,g,85,3", "3,85,g,g", "85,3,g,g"]
    strides = [8, 16, 32]

    print("\n=== Brute-force all layouts ===")
    for layout in layouts:
        all_dets = []
        for si, out_bytes in enumerate(outputs):
            data = np.frombuffer(out_bytes, dtype=np.float32)
            stride = strides[si]
            anchors = YOLOV5_ANCHORS[si]
            try:
                dets = decode_scale(data, stride, anchors, layout)
                all_dets.extend(dets)
            except Exception as e:
                pass

        nms_dets = _nms(all_dets, threshold=0.45, max_det=20)
        if nms_dets:
            print(f"\n*** layout={layout}: {len(nms_dets)} detections ***")
            for d in nms_dets[:10]:
                box, conf, cid = d
                label = COCO_STANDARD[cid] if cid < len(COCO_STANDARD) else f"class_{cid}"
                print(f"  [{cid:2d}] {label}: {conf:.4f} [{box[0]:.0f},{box[1]:.0f},{box[2]:.0f},{box[3]:.0f}]")
        else:
            print(f"layout={layout}: no detections")

    print("\n=== Raw data stats for output 0 (80x80) ===")
    data0 = np.frombuffer(outputs[0], dtype=np.float32)
    print(f"Size: {data0.size}")
    print(f"Min: {data0.min():.6f}, Max: {data0.max():.6f}")
    print(f"Mean: {data0.mean():.6f}, Std: {data0.std():.6f}")
    print(f"Abs > 10: {np.sum(np.abs(data0) > 10)}")
    print(f"Abs > 20: {np.sum(np.abs(data0) > 20)}")

    print("\n=== Sigmoid stats per channel (reshaped as 85,80,80,3) ===")
    out0 = data0.reshape(85, 80, 80, 3)
    for ch in [0, 1, 2, 3, 4]:
        raw = out0[ch, :, :, :]
        sig = _sigmoid(raw)
        print(f"  ch[{ch}] raw: min={raw.min():.4f} max={raw.max():.4f} mean={raw.mean():.4f}")
        print(f"  ch[{ch}] sig: min={sig.min():.4f} max={sig.max():.4f} mean={sig.mean():.4f}")

    print("\n=== Check class channels (sigmoid of 5:85) ===")
    cls_raw = out0[5:85, :, :, :]
    cls_sig = _sigmoid(cls_raw)
    print(f"  Class raw: min={cls_raw.min():.4f} max={cls_raw.max():.4f}")
    print(f"  Class sig: min={cls_sig.min():.4f} max={cls_sig.max():.4f}")
    print(f"  Class sig > 0.5: {np.sum(cls_sig > 0.5)}")
    print(f"  Class sig > 0.3: {np.sum(cls_sig > 0.3)}")

    print("\n=== Alternative: maybe output is already post-processed? ===")
    print("Check if output 0 ch[0] (objectness?) has reasonable values after sigmoid:")
    obj_raw = out0[0, :, :, :]
    obj_sig = _sigmoid(obj_raw)
    print(f"  obj sigmoid > 0.5: {np.sum(obj_sig > 0.5)}")
    print(f"  obj sigmoid > 0.3: {np.sum(obj_sig > 0.3)}")
    print(f"  obj sigmoid > 0.1: {np.sum(obj_sig > 0.1)}")

    print("\n=== Check if any channel has box-like values (tx/ty should be 0-1 after sigmoid, tw/th larger) ===")
    for ch in range(5):
        raw = out0[ch, :, :, :]
        sig = _sigmoid(raw)
        print(f"  ch[{ch}]: raw[{raw.min():.2f}, {raw.max():.2f}] sig[{sig.min():.4f}, {sig.max():.4f}]")


if __name__ == "__main__":
    main()
