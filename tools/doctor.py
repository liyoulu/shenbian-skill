# -*- coding: utf-8 -*-
"""shenbian-skill 环境自检（doctor）

用法（任意目录）:
  python <skill目录>/tools/doctor.py            # 全量检查，输出清单
  python <skill目录>/tools/doctor.py --quiet     # 只有问题时输出（agent 判断用）
  python <skill目录>/tools/doctor.py --json      # 机器可读输出（agent/CI 用）

检查项：深变根目录 / modelhub 模型包 / ffmpeg / CUDA provider / XSeg 模型 /
磁盘空间 /（fork 版额外）3d68 补丁与分片导出。退出码 0=全绿，1=有问题。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(HERE, 'marker_probe')
for p in (HERE, MP):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import _env  # marker_probe 同款环境解析（DFL_ROOT / 自动探测）
except SystemExit as e:
    print(str(e))
    sys.exit(1)


def _read(path, limit=200000):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(limit)
    except OSError:
        return ''


def main():
    ap = argparse.ArgumentParser(description='shenbian-skill 环境自检')
    ap.add_argument('--quiet', action='store_true', help='只有问题时输出')
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    args = ap.parse_args()

    checks = []

    def add(name, ok, detail='', fix=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail, 'fix': fix})

    root = _env.ROOT

    # 1) 深变根目录与入口
    add('dfl_root', os.path.isfile(os.path.join(root, 'main.py')),
        f'{root}', '按上游 README 安装深变（github.com/CaijiPlayer258/DeepFaceLab-PyTorch），并 setx DFL_ROOT "<目录>"')

    # 2) modelhub 关键 onnx（提取链路的最小集）
    need = [
        r'BlazeFace\blaze.onnx',
        r'InsightFace2d106\InsightFace2D106.onnx',
        r'InsightFace3D68\1k3d68.onnx',
        r'FAN\2DFAN.onnx', r'FAN\3DFAN.onnx',
    ]
    missing = [n for n in need if not os.path.isfile(os.path.join(root, 'modelhub', 'onnx', *n.split('\\')))]
    add('modelhub_onnx', not missing,
        '33 个 onnx 中提取链路最小集齐备' if not missing else f'缺 {missing}',
        'modelhub 模型包未装全：按上游 README 从网盘下载 modelhub/ 覆盖到仓库根目录')

    # 3) ffmpeg（含 libplacebo 的 full 版，HDR 提取需要）
    ff = os.path.join(root, 'ffmpeg', 'ffmpeg.exe')
    ff_found = ff if os.path.isfile(ff) else shutil.which('ffmpeg')
    add('ffmpeg', bool(ff_found),
        ff_found or '未找到', '把 gyan.dev full 静态版解压到 <DFL_ROOT>\\ffmpeg\\，或让 ffmpeg 进入 PATH')

    # 4) CUDA provider（onnxruntime 与 torch 的 CUDA 配对）
    cuda, detail = None, ''
    try:
        code = ("import onnxruntime as o;"
                "print(o.__version__ + '|' + ','.join(o.get_available_providers()))")
        r = subprocess.run([sys.executable or _env.PY, '-c', code],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            ver, provs = r.stdout.strip().split('|', 1)
            cuda = 'CUDAExecutionProvider' in provs
            detail = f'onnxruntime {ver} providers={provs}'
        else:
            detail = (r.stderr or r.stdout or 'no output').strip()[:200]
    except Exception as e:  # noqa: BLE001
        detail = f'探测失败: {e}'
    add('cuda_provider', cuda is True,
        detail or '未探测到', 'onnxruntime 未走 CUDA：检查 CUDA/cuDNN 与 onnxruntime-gpu 版本配对（装错会静默退 CPU）')

    # 5) XSeg / XSegLite（项目模型，modelhub 里没有；合成遮罩推荐）
    xs = [n for n in (r'workspace\model\XSeg\xseg.onnx', r'workspace\model\XSeg\XSeg.onnx') if os.path.isfile(os.path.join(root, *n.split('\\')))]
    xl = os.path.isfile(os.path.join(root, 'workspace', 'model', 'XSegLite', 'xseglite.onnx'))
    add('xseg_models', bool(xs) or xl,
        ('XSeg=' + ('有' if xs else '无')) + ' XSegLite=' + ('有' if xl else '无'),
        '从 HuggingFace thinkanameishard/xseg 下载 xseg.onnx / xseglite.onnx，放 workspace\\model\\XSeg\\ 与 XSegLite\\（非必需，但合成质量推荐）')

    # 6) 磁盘余量（帧缓冲粗估：<20GB 警告）
    free_gb = None
    try:
        import ctypes
        f = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(root[:3]), ctypes.byref(f), None, None)
        free_gb = round(f.value / 1024**3, 1)
    except Exception:  # noqa: BLE001
        pass
    add('disk_free', free_gb is None or free_gb >= 20,
        f'{root[:2]} 剩余 {free_gb} GB' if free_gb is not None else '未探测（非 Windows）',
        '磁盘余量 <20GB：清理或换帧缓冲盘（大视频分片导出尤其吃空间）')

    # 7) fork 增强（上游没有不影响使用；有则确认其标志性文件在位）
    dflpng = os.path.isfile(os.path.join(root, 'DFLIMG', 'DFLPNG.py'))
    chunked = os.path.isfile(os.path.join(root, 'MergeStudio', 'core', 'chunked_export.py'))
    patched_3d68 = 'as_float32' in _read(os.path.join(root, 'modelhub', 'onnx', 'InsightFace3D68', 'InsightFace3D68.py'))
    add('fork_extras', True,  # 信息项，不判失败
        f'DFLPNG={dflpng} chunked_export={chunked} 3d68patch={patched_3d68}',
        '这是你 fork 独有增强的在位状态（上游版全部为 False 属正常）')

    if args.json:
        print(json.dumps({'root': root, 'checks': checks}, ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            print(f'shenbian doctor | DFL_ROOT = {root}')
            for c in checks:
                mark = 'OK ' if c['ok'] else 'FAIL'
                print(f'  [{mark}] {c["name"]}: {c["detail"]}')
                if not c['ok'] and c['fix']:
                    print(f'         fix: {c["fix"]}')
        bad = [c for c in checks if not c['ok']]
        if bad:
            print(f'{len(bad)} 项需要处理（--json 看详情）')
    sys.exit(0 if all(c['ok'] for c in checks) else 1)


if __name__ == '__main__':
    main()
