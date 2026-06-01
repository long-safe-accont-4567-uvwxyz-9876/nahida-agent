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


def try_decode(data, layout_func, desc, anchors, stride):
    grid = INPUT_SIZE // stride
    total = 85 * grid * grid * 3
    if data.size < total:
        return []
    reshaped = data.reshape(85, grid, grid, 3)
    gx, gy = np.meshgrid(np.arange(grid), np.arange(grid))
    dets = []
    for ai in range(3):
        aw, ah = anchors[ai]
        obj, tx, ty, tw, th, cls = layout_func(reshaped, ai)
        cx = (_sigmoid(tx) * 2 - 0.5 + gx) * stride
        cy = (_sigmoid(ty) * 2 - 0.5 + gy) * stride
        w = (_sigmoid(tw) * 2) ** 2 * aw
        h = (_sigmoid(th) * 2) ** 2 * ah
        max_cls = np.max(cls, axis=-1)
        conf = obj * max_cls
        mask = conf > 0.3
        indices = np.argwhere(mask)
        for idx in indices:
            yi, xi = int(idx[0]), int(idx[1])
            bw = float(w[yi, xi])
            bh = float(h[yi, xi])
            if bw < 5 or bh < 5:
                continue
            bcx = float(cx[yi, xi])
            bcy = float(cy[yi, xi])
            bconf = float(conf[yi, xi])
            cid = int(np.argmax(cls[yi, xi]))
            dets.append(([bcx - bw/2, bcy - bh/2, bcx + bw/2, bcy + bh/2], bconf, cid))
    return dets


def layout_01234(out, ai):
    return _sigmoid(out[0,:,:,ai]), out[1,:,:,ai], out[2,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_01324(out, ai):
    return _sigmoid(out[0,:,:,ai]), out[1,:,:,ai], out[3,:,:,ai], out[2,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_02134(out, ai):
    return _sigmoid(out[0,:,:,ai]), out[2,:,:,ai], out[1,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_10234(out, ai):
    return _sigmoid(out[1,:,:,ai]), out[0,:,:,ai], out[2,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_10324(out, ai):
    return _sigmoid(out[1,:,:,ai]), out[0,:,:,ai], out[3,:,:,ai], out[2,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_12034(out, ai):
    return _sigmoid(out[1,:,:,ai]), out[2,:,:,ai], out[0,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_12304(out, ai):
    return _sigmoid(out[1,:,:,ai]), out[2,:,:,ai], out[3,:,:,ai], out[0,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_20134(out, ai):
    return _sigmoid(out[2,:,:,ai]), out[0,:,:,ai], out[1,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_23401(out, ai):
    return _sigmoid(out[2,:,:,ai]), out[3,:,:,ai], out[4,:,:,ai], out[0,:,:,ai], out[1,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_34012(out, ai):
    return _sigmoid(out[3,:,:,ai]), out[4,:,:,ai], out[0,:,:,ai], out[1,:,:,ai], out[2,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_04321(out, ai):
    return _sigmoid(out[0,:,:,ai]), out[4,:,:,ai], out[3,:,:,ai], out[2,:,:,ai], out[1,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def layout_obj_xywh_cls_nochange(out, ai):
    return out[0,:,:,ai], out[1,:,:,ai], out[2,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], out[5:85,:,:,ai]

def layout_obj_raw_txty_cls_sigmoid(out, ai):
    return _sigmoid(out[0,:,:,ai]), out[1,:,:,ai], out[2,:,:,ai], out[3,:,:,ai], out[4,:,:,ai], _sigmoid(out[5:85,:,:,ai])

def _iou(a, b):
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0

def nms(dets, thresh=0.45, max_det=20):
    if not dets:
        return []
    dets.sort(key=lambda d: d[1], reverse=True)
    dets = dets[:max_det*3]
    keep = []
    while dets:
        best = dets.pop(0)
        keep.append(best)
        if len(keep) >= max_det:
            break
        dets = [d for d in dets if _iou(best[0], d[0]) < thresh]
    return keep


model = NPUModel(MODEL_PATH)
if not model.loaded:
    print('FAIL')
    exit(1)

img = cv2.imread(TEST_IMAGE)
img_r = cv2.resize(img, (INPUT_SIZE, INPUT_SIZE))
img_rgb = cv2.cvtColor(img_r, cv2.COLOR_BGR2RGB)
input_bytes = img_rgb.astype(np.uint8).tobytes()
outputs = model.run(input_bytes)

strides = [8, 16, 32]
layouts = [
    ("01234", layout_01234),
    ("01324", layout_01324),
    ("02134", layout_02134),
    ("10234", layout_10234),
    ("10324", layout_10324),
    ("12034", layout_12034),
    ("12304", layout_12304),
    ("20134", layout_20134),
    ("23401", layout_23401),
    ("34012", layout_34012),
    ("04321", layout_04321),
    ("no_sigmoid", layout_obj_xywh_cls_nochange),
    ("obj_sigmoid_cls_sigmoid", layout_obj_raw_txty_cls_sigmoid),
]

for name, func in layouts:
    all_dets = []
    for si in range(3):
        data = np.frombuffer(outputs[si], dtype=np.float32)
        try:
            dets = try_decode(data, func, name, YOLOV5_ANCHORS[si], strides[si])
            all_dets.extend(dets)
        except:
            pass
    nms_d = nms(all_dets)
    if nms_d:
        print(f"\n*** {name}: {len(nms_d)} detections ***")
        for d in nms_d[:5]:
            box, conf, cid = d
            label = COCO_ALPHA[cid] if cid < len(COCO_ALPHA) else f"c{cid}"
            print(f"  [{cid:2d}] {label}: {conf:.3f} [{box[0]:.0f},{box[1]:.0f},{box[2]:.0f},{box[3]:.0f}]")
    else:
        print(f"{name}: 0 detections")

print("\n=== What if the 85 channels are NOT obj+tx+ty+tw+th+cls but something else? ===")
print("=== What if the model output is (3, 85, grid, grid) in memory? ===")
for si in range(3):
    data = np.frombuffer(outputs[si], dtype=np.float32)
    grid = INPUT_SIZE // strides[si]
    total = 85 * grid * grid * 3
    if data.size < total:
        continue
    reshaped_85_3 = data.reshape(85, 3, grid, grid)
    print(f"\n  Scale {si}: checking if 85 is the first dim, 3 is anchor")
    for ch in range(5):
        raw = reshaped_85_3[ch, 0, :, :]
        sig = _sigmoid(raw)
        print(f"    ch[{ch}] raw range: [{raw.min():.4f}, {raw.max():.4f}] sig range: [{sig.min():.4f}, {sig.max():.4f}]")

print("\n=== Check: is there a pattern where channels are interleaved per-anchor? ===")
print("E.g., output might be: (anchor0_obj, anchor0_tx, anchor0_ty, anchor0_tw, anchor0_th, anchor0_cls..., anchor1_obj, ...)")
for si in range(3):
    data = np.frombuffer(outputs[si], dtype=np.float32)
    grid = INPUT_SIZE // strides[si]
    total = 85 * grid * grid * 3
    if data.size < total:
        continue
    print(f"\n  Scale {si} (grid={grid}): trying per-anchor 85-chunk layout")
    for ai in range(3):
        start = ai * 85 * grid * grid
        chunk = data[start:start + 85 * grid * grid]
        if chunk.size < 85 * grid * grid:
            continue
        out = chunk.reshape(85, grid, grid)
        obj_raw = out[0, :, :]
        obj_sig = _sigmoid(obj_raw)
        w_raw = out[3, :, :]
        h_raw = out[4, :, :]
        w_sig = _sigmoid(w_raw)
        h_sig = _sigmoid(h_raw)
        print(f"    Anchor {ai}: obj_sig max={obj_sig.max():.4f}, w_sig max={w_sig.max():.4f}, h_sig max={h_sig.max():.4f}")

print("\n=== Check: maybe the last dim '1' in [85,80,80,3,1] means something ===")
print("=== What if we should reshape as (85*3, 80, 80) or (3, 85, 80, 80)? ===")
for si in range(3):
    data = np.frombuffer(outputs[si], dtype=np.float32)
    grid = INPUT_SIZE // strides[si]
    try:
        reshaped_a = data.reshape(85, 3, grid, grid)
        reshaped_b = data.reshape(3, 85, grid, grid)
        reshaped_c = data.reshape(255, grid, grid)
        reshaped_d = data.reshape(grid, grid, 255)

        for name, r in [("85,3,g,g", reshaped_a), ("3,85,g,g", reshaped_b), ("255,g,g", reshaped_c), ("g,g,255", reshaped_d)]:
            print(f"  Scale {si} reshape {name}: range [{r.min():.4f}, {r.max():.4f}]")
    except Exception as e:
        print(f"  Scale {si}: error {e}")
