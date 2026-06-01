#!/usr/bin/env python3
import numpy as np
import cv2
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from npu_inference import NPUModel, VIPLite, INPUT_SIZE, _sigmoid, vip_buffer_create_params_t, \
    VIP_BUFFER_FORMAT_UINT8, VIP_BUFFER_FORMAT_FP32, VIP_BUFFER_QUANTIZE_TF_ASYMM, \
    VIP_BUFFER_QUANTIZE_NONE, VIP_BUFFER_MEMORY_TYPE_DEFAULT, VIP_BUFFER_OPER_TYPE_FLUSH, \
    VIP_BUFFER_OPER_TYPE_INVALIDATE

MODEL_PATH = '/home/orangepi/ai-agent/models/yolov5.nb'
TEST_IMAGE = '/opt/yolov5/input_data/dog_640_640.jpg'

YOLOV5_ANCHORS = [
    [(10, 13), (16, 30), (33, 23)],
    [(30, 61), (62, 45), (59, 119)],
    [(116, 90), (156, 198), (373, 326)],
]


def run_model(img_rgb, preprocess_mode):
    if preprocess_mode == "uint8_rgb":
        input_bytes = img_rgb.astype(np.uint8).tobytes()
    elif preprocess_mode == "float_chw":
        img_f = img_rgb.astype(np.float32) / 255.0
        img_f = img_f.transpose(2, 0, 1)
        input_bytes = img_f.tobytes()
    elif preprocess_mode == "uint8_rgb_nchw":
        img_t = img_rgb.transpose(2, 0, 1)
        input_bytes = img_t.astype(np.uint8).tobytes()
    else:
        input_bytes = img_rgb.astype(np.uint8).tobytes()

    vip = VIPLite()
    if not vip.available:
        return None
    vip.init()
    network = vip.create_network(MODEL_PATH)
    if not network:
        return None
    if not vip.prepare_network(network):
        return None

    num_inputs = vip.query_network_u32(network, 1)
    num_outputs = vip.query_network_u32(network, 2)

    input_buffers = []
    for i in range(num_inputs):
        ndims = vip.query_input_u32(network, i, 1)
        sizes = vip.query_input_sizes(network, i)[:ndims]
        fmt = vip.query_input_u32(network, i, 3)
        qfmt = vip.query_input_u32(network, i, 0)
        params = vip_buffer_create_params_t()
        params.num_of_dims = ndims
        for j, s in enumerate(sizes):
            params.sizes[j] = s
        params.data_format = fmt
        params.quant_format = qfmt
        if qfmt == 2:
            params.quant_data.affine.scale = vip.query_input_float(network, i, 5)
            params.quant_data.affine.zeroPoint = vip.query_input_u32(network, i, 6)
        params.memory_type = 0
        buf = vip.create_buffer(params)
        if buf:
            input_buffers.append((buf, sizes, fmt, qfmt))
            vip.set_input(network, i, buf)

    output_buffers = []
    for i in range(num_outputs):
        ndims = vip.query_output_u32(network, i, 1)
        sizes = vip.query_output_sizes(network, i)[:ndims]
        fmt = vip.query_output_u32(network, i, 3)
        qfmt = vip.query_output_u32(network, i, 0)
        params = vip_buffer_create_params_t()
        params.num_of_dims = ndims
        for j, s in enumerate(sizes):
            params.sizes[j] = s
        params.data_format = fmt
        params.quant_format = qfmt
        if qfmt == 2:
            params.quant_data.affine.scale = vip.query_output_float(network, i, 5)
            params.quant_data.affine.zeroPoint = vip.query_output_u32(network, i, 6)
        params.memory_type = 0
        buf = vip.create_buffer(params)
        if buf:
            output_buffers.append((buf, sizes, fmt, qfmt))
            vip.set_output(network, i, buf)

    ibuf = input_buffers[0][0]
    mapped = vip.map_buffer(ibuf)
    bsize = vip.get_buffer_size(ibuf)
    ctypes.memmove(mapped, input_bytes, min(len(input_bytes), bsize))
    vip.flush_buffer(ibuf, VIP_BUFFER_OPER_TYPE_FLUSH)

    vip.run_network(network)

    results = []
    for obuf, osizes, ofmt, oqfmt in output_buffers:
        vip.flush_buffer(obuf, VIP_BUFFER_OPER_TYPE_INVALIDATE)
        mapped_out = vip.map_buffer(obuf)
        out_size = vip.get_buffer_size(obuf)
        out_data = (ctypes.c_uint8 * out_size)()
        ctypes.memmove(out_data, mapped_out, out_size)
        arr = np.frombuffer(bytes(out_data), dtype=np.float32)
        results.append(arr)

    vip.finish_network(network)
    vip.destroy_network(network)

    return results, input_buffers[0][1:]


import ctypes


def analyze_detections(outputs, preprocess_mode):
    strides = [8, 16, 32]

    print(f"\n=== Preprocess: {preprocess_mode} ===")
    for si, data in enumerate(outputs):
        stride = strides[si]
        grid = INPUT_SIZE // stride
        total = 85 * grid * grid * 3
        if data.size < total:
            print(f"  Scale {si}: insufficient data {data.size} < {total}")
            continue

        reshaped = data.reshape(85, grid, grid, 3)
        obj = _sigmoid(reshaped[0, :, :, :])
        tx_raw = reshaped[1, :, :, :]
        ty_raw = reshaped[2, :, :, :]
        tw_raw = reshaped[3, :, :, :]
        th_raw = reshaped[4, :, :, :]

        gx, gy = np.meshgrid(np.arange(grid), np.arange(grid))
        for ai in range(3):
            aw, ah = YOLOV5_ANCHORS[si][ai]
            o = obj[:, :, ai]
            tx = tx_raw[:, :, ai]
            ty = ty_raw[:, :, ai]
            tw = tw_raw[:, :, ai]
            th = th_raw[:, :, ai]

            cx = (_sigmoid(tx) * 2 - 0.5 + gx) * stride
            cy = (_sigmoid(ty) * 2 - 0.5 + gy) * stride
            w = (_sigmoid(tw) * 2) ** 2 * aw
            h = (_sigmoid(th) * 2) ** 2 * ah

            high_mask = o > 0.5
            count = np.sum(high_mask)
            if count > 0:
                max_o = o.max()
                mean_w = w[high_mask].mean() if count > 0 else 0
                mean_h = h[high_mask].mean() if count > 0 else 0
                print(f"  Scale {si} Anchor {ai}: {count} high-obj, max_obj={max_o:.4f}, mean_w={mean_w:.1f}, mean_h={mean_h:.1f}")


img = cv2.imread(TEST_IMAGE)
img_resized = cv2.resize(img, (INPUT_SIZE, INPUT_SIZE))
img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

for mode in ["uint8_rgb", "float_chw", "uint8_rgb_nchw"]:
    try:
        outputs, input_info = run_model(img_rgb, mode)
        print(f"\nInput info for {mode}: {input_info}")
        analyze_detections(outputs, mode)
    except Exception as e:
        print(f"\n{mode}: ERROR {e}")

print("\n=== Test: what if the model expects NHWC uint8 input but we need to provide pre-processed float? ===")
vip = VIPLite()
vip.init()
net = vip.create_network(MODEL_PATH)
if net:
    vip.prepare_network(net)
    ndims = vip.query_input_u32(net, 0, 1)
    sizes = vip.query_input_sizes(net, 0)[:ndims]
    fmt = vip.query_input_u32(net, 0, 3)
    qfmt = vip.query_input_u32(net, 0, 0)
    scale = vip.query_input_float(net, 0, 5) if qfmt == 2 else 1.0
    zp = vip.query_input_u32(net, 0, 6) if qfmt == 2 else 0
    print(f"Input: ndims={ndims}, sizes={sizes}, fmt={fmt}, qfmt={qfmt}, scale={scale}, zp={zp}")

    for oi in range(vip.query_network_u32(net, 2)):
        ondims = vip.query_output_u32(net, oi, 1)
        osizes = vip.query_output_sizes(net, oi)[:ondims]
        ofmt = vip.query_output_u32(net, oi, 3)
        oqfmt = vip.query_output_u32(net, oi, 0)
        oscale = vip.query_output_float(net, oi, 5) if oqfmt == 2 else 1.0
        ozp = vip.query_output_u32(net, oi, 6) if oqfmt == 2 else 0
        print(f"Output {oi}: ndims={ondims}, sizes={osizes}, fmt={ofmt}, qfmt={oqfmt}, scale={oscale}, zp={ozp}")

    vip.finish_network(net)
    vip.destroy_network(net)
