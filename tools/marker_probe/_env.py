# -*- coding: utf-8 -*-
"""环境解析：找到 DeepFaceLab-PyTorch（深变）仓库根目录。

优先级：环境变量 DFL_ROOT > 常见位置探测 > 报错退出。
所有 marker_probe 脚本 import 本模块后即可使用 ROOT / MD / PY / WS：
  ROOT = 深变仓库根目录（已插入 sys.path，可直接 import modelhub/facelib/MergeStudio）
  MD   = modelhub/onnx 模型目录
  PY   = 深变自带 python.exe（不存在则退回当前解释器）
  WS   = 本目录下 _work\，脚本的输出/缓存落这里

selfcheck(): 快速验证提取链路最小依赖，供各工具 --check 调用。
"""
import os
import sys


def _find_root():
    env = os.environ.get('DFL_ROOT')
    if env and os.path.isfile(os.path.join(env, 'main.py')):
        return os.path.abspath(env)
    strict = os.environ.get('SHENBIAN_STRICT_ROOT')  # 测试/沙箱：不回退探测
    if not strict:
        for cand in (r'F:\DFL-PyTorch', r'C:\DFL-PyTorch', r'D:\DFL-PyTorch',
                     os.path.join(os.path.expanduser('~'), 'DFL-PyTorch')):
            if os.path.isfile(os.path.join(cand, 'main.py')):
                return os.path.abspath(cand)
    sys.exit('[marker_probe] 找不到 DeepFaceLab-PyTorch 仓库根目录。'
             '请先安装深变（github.com/CaijiPlayer258/DeepFaceLab-PyTorch），'
             '并设置环境变量 DFL_ROOT 指向包含 main.py 的目录。')


ROOT = _find_root()
MD = os.path.join(ROOT, 'modelhub', 'onnx')
_py = os.path.join(ROOT, 'python', 'python.exe')
PY = _py if os.path.isfile(_py) else sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(HERE, '_work')
os.makedirs(WS, exist_ok=True)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def selfcheck():
    """提取链路最小依赖自检。返回 (ok: bool, lines: list[str])。"""
    lines, ok = [], True
    lines.append(f'DFL_ROOT = {ROOT}')

    def item(name, good, detail, fix=''):
        nonlocal ok
        if not good:
            ok = False
        lines.append(f'  [{"OK" if good else "FAIL"}] {name}: {detail}' + (f'  (fix: {fix})' if not good and fix else ''))

    item('repo entry', os.path.isfile(os.path.join(ROOT, 'main.py')), ROOT)
    for rel in (r'BlazeFace\blaze.onnx', r'InsightFace2d106\InsightFace2D106.onnx',
                r'InsightFace3D68\1k3d68.onnx', r'FAN\2DFAN.onnx', r'FAN\3DFAN.onnx'):
        item('onnx ' + rel.split('\\')[0], os.path.isfile(os.path.join(MD, *rel.split('\\'))),
             rel, 'modelhub 模型包未装全，见上游 README')
    try:
        import onnxruntime as o
        provs = o.get_available_providers()
        item('onnxruntime', 'CUDAExecutionProvider' in provs or 'CPUExecutionProvider' in provs,
             f'{o.__version__} providers={",".join(provs)}',
             'CUDAExecutionProvider 缺失时推理会退 CPU（可用但慢）')
    except Exception as e:  # noqa: BLE001
        item('onnxruntime', False, f'导入失败: {e}', '在深变环境里运行本脚本')
    return ok, lines
