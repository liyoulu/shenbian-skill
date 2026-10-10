# -*- coding: utf-8 -*-
"""
人脸拼图（contact sheet）工具 —— 目检脸集用。两种模式自动切换：

  分组模式：目录里有 faceid_group_* / faceid_noise 等子目录 → **每个子目录出一张拼图**
            （适合身份聚类后挑人，标出组名/张数/占比）
  平铺模式：目录里直接是脸图 → **出一张总览拼图**
            （适合看切脸质量/取景一致性）

用法：
  python make_id_contactsheet.py <脸集目录> [--out 输出目录] [--cols 4] [--rows 3]
                                 [--cell 200] [--seed 0] [--pattern "*.jpg"]
                                 [--mode auto|group|flat] [--title "自定义标题"]

例：
  # 身份聚类后：每个组一张拼图，输出到 <目录>\\_idcheck\\
  python make_contact_sheet.py "<aligned目录>"

  # 平铺总览（例如切完脸看质量），输出到指定目录
  python make_contact_sheet.py "<aligned目录>" --out "<输出目录>"

注意：
- 拼图输出目录**不要放在 aligned 里面**——后续 `Filter.py --merge-only` 会把子目录当组卷回脸集；
- 读图用 np.fromfile + imdecode，支持中文/表情符路径；
- 采样是等间隔 + 固定 seed，结果可复现。
"""
import sys, os, glob, argparse
import numpy as np
import cv2


def imread_u(p):
    try:
        buf = np.fromfile(p, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR) if buf.size else None
    except Exception:
        return None


def sheet(files, cols, rows, cell, title):
    n = min(cols * rows, len(files))
    idx = np.linspace(0, len(files) - 1, n).astype(int)
    canvas = np.zeros((cell * rows + 34, cell * cols, 3), np.uint8)
    for k, i in enumerate(idx):
        im = imread_u(files[i])
        if im is None:
            continue
        h, w = im.shape[:2]
        s = cell / float(max(h, w))
        im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
        r, c = divmod(k, cols)
        y = 34 + r * cell + (cell - im.shape[0]) // 2
        x = c * cell + (cell - im.shape[1]) // 2
        canvas[y:y + im.shape[0], x:x + im.shape[1]] = im
    cv2.putText(canvas, title, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


ap = argparse.ArgumentParser()
ap.add_argument('root', help='脸集目录')
ap.add_argument('--out', default='', help='输出目录（默认 <root>\\_idcheck）')
ap.add_argument('--cols', type=int, default=4)
ap.add_argument('--rows', type=int, default=3)
ap.add_argument('--cell', type=int, default=200, help='每格边长像素')
ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--pattern', default='*.jpg', help='匹配模式，可用逗号分隔，如 "*.jpg,*.png"')
ap.add_argument('--mode', choices=['auto', 'group', 'flat'], default='auto')
ap.add_argument('--title', default='', help='平铺模式的自定义标题')
args = ap.parse_args()

root = os.path.abspath(args.root)
if not os.path.isdir(root):
    sys.exit('目录不存在: %s' % root)
out = args.out or os.path.join(root, '_idcheck')
os.makedirs(out, exist_ok=True)
np.random.seed(args.seed)

pats = [p.strip() for p in args.pattern.split(',') if p.strip()]
subs = sorted([d for d in glob.glob(os.path.join(root, '*')) if os.path.isdir(d)
               and os.path.basename(d).startswith(('faceid_group_', 'faceid_noise', 'group_'))])
mode = args.mode
if mode == 'auto':
    mode = 'group' if subs else 'flat'
print('模式: %s   输出: %s' % (mode, out))


def collect(d, recurse=False):
    fs = []
    for p in pats:
        fs += glob.glob(os.path.join(d, '**', p) if recurse else os.path.join(d, p), recursive=recurse)
    return sorted(set(fs))


if mode == 'group' and subs:
    total = sum(len(collect(s, True)) for s in subs)
    if total == 0:
        total = len(collect(root))
    made = 0
    for d in subs:
        fs = collect(d, True)
        if not fs:
            continue
        name = os.path.basename(d)
        pct = 100.0 * len(fs) / max(1, total)
        img = sheet(fs, args.cols, args.rows, args.cell, '%s  %d faces (%.1f%%)' % (name, len(fs), pct))
        p = os.path.join(out, name + '.png')
        cv2.imwrite(p, img)
        print('  %-26s %6d 张 → %s' % (name, len(fs), p))
        made += 1
    print('共 %d 张拼图' % made)
else:
    fs = collect(root)
    if not fs:
        sys.exit('目录里没找到匹配的图片（pattern=%s）' % args.pattern)
    title = args.title or '%s  %d faces' % (os.path.basename(root), len(fs))
    img = sheet(fs, args.cols, args.rows, args.cell, title)
    p = os.path.join(out, 'overview_%s.png' % os.path.basename(root))
    cv2.imwrite(p, img)
    print('  %d 张脸抽样 → %s' % (min(args.cols * args.rows, len(fs)), p))
