# -*- coding: utf-8 -*-
"""标记点测试共用工具：非 ASCII 路径读图、4 个标记点推理（2d106 已做 106→68 映射）、Procrustes 指标。
注意：insightface-2d106det 的原始输出是 **106 点布局**，必须经 landmark106to68 映射后才能当 68 用；
映射表取自深变仓库 Extractor/Extractor.py（作者标注"这个我能确保是包对的"）。
"""
import sys, os
import _env
import numpy as np, cv2
import onnxruntime as ort
from xlib.onnxruntime import get_cpu_device_info
from modelhub.onnx.BlazeFace.BlazeFace import BlazeFace

MD = _env.MD

LANDMARK106TO68 = [
    1, 10, 12, 14, 16, 3, 5, 7, 0,
    23, 21, 19, 32, 30, 28, 26, 17,
    43, 48, 49, 51, 50,
    102, 103, 104, 105, 101,
    72, 73, 74, 86, 78, 79, 80, 85, 84,
    35, 41, 42, 39, 37, 36,
    89, 95, 96, 93, 91, 90,
    52, 64, 63, 71, 67, 68, 61, 58, 59, 53, 56, 55, 65, 66, 62, 70, 69, 57, 60, 54,
]


def landmark106to68(pt106):
    if len(pt106) != 106:
        return pt106[:68]
    return np.array([pt106[i] for i in LANDMARK106TO68])


def imread_u(path):
    """Windows 非 ASCII 路径安全的读图"""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR) if buf.size else None
    except Exception:
        return None


_det = None


def detector():
    global _det
    if _det is None:
        _det = BlazeFace(get_cpu_device_info())
    return _det


def biggest(img):
    r = detector().extract(img)
    if not r:
        return None
    b = r[0] if isinstance(r[0], list) else r
    return max(b, key=lambda x: (x[2] - x[0]) * (x[3] - x[1])) if len(b) else None


def crop_face(img, margin=0.4, min_side=120):
    b = biggest(img)
    if b is None:
        return None
    cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
    half = int(max(b[2] - b[0], b[3] - b[1]) * 0.5 * (1.0 + margin))
    l, t = max(0, cx - half), max(0, cy - half)
    c = img[t:t + 2 * half, l:l + 2 * half]
    return c if c.shape[0] >= min_side and c.shape[1] >= min_side else None


_S = {}


def _sess(key, path):
    if key not in _S:
        _S[key] = ort.InferenceSession(os.path.join(MD, path), providers=['CPUExecutionProvider'])
    return _S[key]


def run_2d106(crop):
    """返回裁剪像素坐标的 68 点（已 106→68 映射）"""
    s = _sess('2d106', r'InsightFace2d106\InsightFace2D106.onnx')
    H, W = crop.shape[:2]
    x = cv2.resize(crop, (192, 192)).astype(np.float32)[:, :, ::-1]     # RGB 0..255
    o = s.run(None, {s.get_inputs()[0].name:
                     np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None])})[0][0]
    pts106 = (o.reshape(-1, 2) / 2.0 + 0.5) * (W, H)
    return landmark106to68(pts106)


def run_2d106_raw(crop):
    """未映射的 106 点（复现仓库 wrapper 的返回）"""
    s = _sess('2d106', r'InsightFace2d106\InsightFace2D106.onnx')
    H, W = crop.shape[:2]
    x = cv2.resize(crop, (192, 192)).astype(np.float32)[:, :, ::-1]
    o = s.run(None, {s.get_inputs()[0].name:
                     np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None])})[0][0]
    return (o.reshape(-1, 2) / 2.0 + 0.5) * (W, H)


def run_3d68(crop):
    s = _sess('3d68', r'InsightFace3D68\1k3d68.onnx')
    H, W = crop.shape[:2]
    x = cv2.resize(crop, (192, 192)).astype(np.float32)                 # BGR 0..255（已修复量纲）
    o = s.run(None, {s.get_inputs()[0].name:
                     np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None])})[0][0]
    p = np.asarray(o).reshape(-1, 3)[-68:, :2].astype(np.float64)
    return (p + 1.0) * (W, H) / 2.0


def run_fan(which):
    key = 'fan2' if which == 2 else 'fan3'
    s = _sess(key, r'FAN\%s.onnx' % ('2DFAN' if which == 2 else '3DFAN'))

    def f(crop):
        H, W = crop.shape[:2]
        x = cv2.resize(crop, (256, 256)).astype(np.float32) / 255.0     # BGR [0,1]
        hm = np.asarray(s.run(None, {s.get_inputs()[0].name:
                                     np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None])})[0][0]
                        ).reshape(68, -1)
        idx = hm.argmax(1)
        return np.column_stack([idx % 64, idx // 64]).astype(np.float64) / 64.0 * (W, H)
    return f


def umeyama(src, dst):
    src = np.asarray(src, np.float64); dst = np.asarray(dst, np.float64)
    n = src.shape[0]
    mus, mud = src.mean(0), dst.mean(0)
    sc, dc = src - mus, dst - mud
    U, D, Vt = np.linalg.svd(dc.T @ sc / n)
    S = np.eye(2)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[1, 1] = -1
    R = U @ S @ Vt
    scale = (D * np.diag(S)).sum() / ((sc ** 2).sum() / n)
    return np.hstack([scale * R, (mud - scale * R @ mus)[:, None]])


def rms_iod(a, b, idx=slice(17, 68)):
    """相似变换对齐后 RMS / 双眼间距"""
    a, b = np.asarray(a, np.float64)[idx], np.asarray(b, np.float64)[idx]
    M = umeyama(a, b)
    fit = (M[:, :2] @ a.T).T + M[:, 2]
    iod = np.linalg.norm(b[36 - idx.start:42 - idx.start].mean(0)
                         - b[42 - idx.start:48 - idx.start].mean(0)) if idx.start <= 36 else 1.0
    return np.sqrt(((fit - b) ** 2).sum(1).mean()) / iod


def consensus_residual(pts_dict, target, idx=slice(0, 64)):
    """留一法：其余标记点逐点中位数为共识"""
    others = [np.asarray(v, np.float64)[idx] for k, v in pts_dict.items() if k != target]
    cons = np.median(np.stack(others), axis=0)
    return rms_iod(np.asarray(pts_dict[target], np.float64), cons, idx)
