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

COCO_ALPHA = [
    "airplane", "apple", "backpack", "banana", "baseball bat", "baseball glove",
    "bear", "bench", "bicycle", "bird", "boat", "book", "bottle", "bowl",
    "broccoli", "cake", "carrot", "cell phone", "chair", "clock", "couch",
    "dining table", "donut", "elephant", "fire hydrant", "fork", "frisbee",
    "giraffe", "hair drier", "handbag", "horse", "hot dog", "keyboard", "kite",
    "knife", "laptop", "microwave", "motorcycle", "mouse", "orange", "oven",
    "parking meter", "person", "pizza", "potted plant", "refrigerator", "remote",
    "sandwich", "scissors", "sheep", "sink", "skateboard", "skis", "snowboard",
    "spoon", "sports ball", "stop sign", "suitcase", "surfboard", "teddy bear",
    "tennis racket", "toaster", "toilet", "toothbrush", "traffic light", "train",
    "truck", "umbrella", "vase", "wine glass",
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
    data0 = np.frombuffer(outputs[0], dtype=np.float32)
    out0 = data0.reshape(85, 80, 80, 3)

    print("=== Layout 85,g,g,3: channel-by-channel analysis ===")
    print("\n--- Channel 0 (supposed obj) per-anchor ---")
    for ai in range(3):
        ch = out0[0, :, :, ai]
        sig = _sigmoid(ch)
        print(f"  anchor {ai}: raw[{ch.min():.4f}, {ch.max():.4f}] sig[{sig.min():.4f}, {sig.max():.4f}] >0.5:{np.sum(sig>0.5)}")

    print("\n--- Channel 1 (tx) per-anchor ---")
    for ai in range(3):
        ch = out0[1, :, :, ai]
        sig = _sigmoid(ch)
        print(f"  anchor {ai}: raw[{ch.min():.4f}, {ch.max():.4f}] sig[{sig.min():.4f}, {sig.max():.4f}]")

    print("\n--- Find top-20 highest objectness positions in anchor 0 ---")
    obj0 = _sigmoid(out0[0, :, :, 0])
    flat_idx = np.argsort(obj0.ravel())[::-1][:20]
    for fi in flat_idx:
        yi = fi // 80
        xi = fi % 80
        print(f"  grid[{yi},{xi}]: obj={obj0[yi,xi]:.4f} raw_ch0={out0[0,yi,xi,0]:.4f}")
        for c in range(5):
            print(f"    ch[{c}]={out0[c,yi,xi,0]:.4f} sig={_sigmoid(out0[c,yi,xi,0]):.4f}")
        cls_raw = out0[5:85, yi, xi, 0]
        cls_sig = _sigmoid(cls_raw)
        top3 = np.argsort(cls_sig)[::-1][:3]
        for t in top3:
            print(f"    class[{t}]={cls_sig[t]:.4f} raw={cls_raw[t]:.4f}")

    print("\n=== Try all 80 possible channel-to-class mappings ===")
    for stride_idx, stride in enumerate([8, 16, 32]):
        data = np.frombuffer(outputs[stride_idx], dtype=np.float32)
        grid = INPUT_SIZE // stride
        total = 85 * grid * grid * 3
        if data.size < total:
            continue
        reshaped = data.reshape(85, grid, grid, 3)

        print(f"\n--- Scale {stride_idx} (stride={stride}, grid={grid}) ---")
        for anchor_idx in range(3):
            obj = _sigmoid(reshaped[0, :, :, anchor_idx])
            high_obj_mask = obj > 0.3
            count = np.sum(high_obj_mask)
            if count == 0:
                continue
            high_idx = np.argwhere(high_obj_mask)
            print(f"  Anchor {anchor_idx}: {count} positions with obj>0.3")
            for hi in high_idx[:3]:
                yi, xi = int(hi[0]), int(hi[1])
                tx = reshaped[1, yi, xi, anchor_idx]
                ty = reshaped[2, yi, xi, anchor_idx]
                tw = reshaped[3, yi, xi, anchor_idx]
                th = reshaped[4, yi, xi, anchor_idx]
                cx = (_sigmoid(tx) * 2 - 0.5 + xi) * stride
                cy = (_sigmoid(ty) * 2 - 0.5 + yi) * stride
                w = (_sigmoid(tw) * 2) ** 2 * YOLOV5_ANCHORS[stride_idx][anchor_idx][0]
                h = (_sigmoid(th) * 2) ** 2 * YOLOV5_ANCHORS[stride_idx][anchor_idx][1]
                cls_raw = reshaped[5:85, yi, xi, anchor_idx]
                cls_sig = _sigmoid(cls_raw)
                top_cls = np.argmax(cls_sig)
                top_conf = cls_sig[top_cls]
                print(f"    [{yi},{xi}] obj={obj[yi,xi]:.4f} box=({cx:.0f},{cy:.0f},{w:.0f},{h:.0f}) cls_std={top_cls}({COCO_STANDARD[top_cls]})={top_conf:.4f} cls_a={top_cls}({COCO_ALPHA[top_cls] if top_cls < len(COCO_ALPHA) else '?'})={top_conf:.4f}")

    print("\n=== Maybe this model is NOT YOLOv5 standard format ===")
    print("Checking if output could be a single concatenated detection tensor...")
    for scale_idx in range(3):
        data = np.frombuffer(outputs[scale_idx], dtype=np.float32)
        grid = [80, 40, 20][scale_idx]
        stride = [8, 16, 32][scale_idx]
        print(f"\n  Scale {scale_idx}: {data.size} floats, stride={stride}, grid={grid}")
        print(f"    85*{grid}*{grid}*3 = {85*grid*grid*3}")
        print(f"    5*{grid}*{grid}*3 + 80*{grid}*{grid}*3 = {5*grid*grid*3 + 80*grid*grid*3}")


if __name__ == "__main__":
    main()
