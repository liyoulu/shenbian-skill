# -*- coding: utf-8 -*-
"""环境解析：找到 DeepFaceLab-PyTorch（深变）仓库根目录。

优先级：环境变量 DFL_ROOT > 常见位置探测 > 报错退出。
所有 marker_probe 脚本 import 本模块后即可使用 ROOT / MD / PY / WS：
  ROOT = 深变仓库根目录（已插入 sys.path，可直接 import modelhub/facelib/MergeStudio）
  MD   = modelhub/onnx 模型目录
  PY   = 深变自带 python.exe（不存在则退回当前解释器）
  WS   = 本目录下 _work\，脚本的输出/缓存落这里
"""
import os
import sys


def _find_root():
    env = os.environ.get('DFL_ROOT')
    if env and os.path.isfile(os.path.join(env, 'main.py')):
        return os.path.abspath(env)
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
