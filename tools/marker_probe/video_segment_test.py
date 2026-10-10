# -*- coding: utf-8 -*-
"""
真实片源抽样测试：取视频一小段 → ffmpeg 抽帧 → 多个检测器逐一跑 →
用"全体检测器的共识框"估人脸占画面比例，再按比例分箱统计**每个检测器的检出率**
（专门回答"近景特写帧会不会漏检"）。

用法（工作目录任意）：
  python video_segment_test.py --video "<视频路径>" `
      [--start 00:00:10] [--dur 8] [--fps 2] [--max-width 1920] `
      [--detectors TinyMog,YoloV8Face,RetinaFace_10g,DamoFD,S3FD] [--keep-frames]

说明：
- 帧按原分辨率（--max-width 可限制）送检测器，与 Extractor 默认 one_stage/input_size=640 一致；
- 参考占比 = 各检测器"最大框宽/图宽"的中位数（检测器口径不同，取中位更稳），据此分箱；
- 结果写同目录 video_segment_report.txt。
"""
import sys, os, argparse, subprocess, glob, time
import _env
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import _env  # noqa: F401  (环境解析；--check 在 argparse 后处理)
import argparse as _argparse
if '--check' not in sys.argv:
    import mk_common as M
    from xlib.onnxruntime import get_cpu_device_info
    from MergeStudio.core.detector.factory import DetectorFactory

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(_env.ROOT, 'ffmpeg', 'ffmpeg.exe')
if not os.path.exists(FFMPEG):
    FFMPEG = 'ffmpeg'
LOG = []


def say(s):
    print(s, flush=True)
    LOG.append(s)


def norm_boxes(raw):
    if raw is None:
        return []
    if isinstance(raw, np.ndarray):
        raw = [raw]
    if len(raw) > 0 and isinstance(raw[0], list) and len(np.asarray(raw[0]).shape) == 3:
        raw = raw[0]
    out = []
    for it in raw:
        if isinstance(it, (tuple, list)) and len(it) == 2 and np.asarray(it[0]).size == 4:
            out.append(np.asarray(it[0], np.float64).ravel())
        else:
            a = np.asarray(it, np.float64).ravel()
            if a.size >= 4:
                out.append(a[:4])
    return out


ap = argparse.ArgumentParser()
ap.add_argument('--video', required=False)
ap.add_argument('--check', action='store_true', help='环境自检后退出（不处理视频）')
ap.add_argument('--start', default='00:00:05')
ap.add_argument('--dur', type=float, default=8.0)
ap.add_argument('--fps', type=float, default=2.0)
ap.add_argument('--max-width', type=int, default=1920)
ap.add_argument('--detectors', default='TinyMog,YoloV8Face,RetinaFace_10g,S3FD')
ap.add_argument('--keep-frames', action='store_true')
args = ap.parse_args()
if getattr(args, 'check', False):
    import _env
    ok, lines_ = _env.selfcheck()
    print('\n'.join(lines_))
    sys.exit(0 if ok else 2)
if not os.path.exists(args.video):
    sys.exit('视频不存在: %s' % args.video)

fdir = os.path.join(HERE, '_vframes')
os.makedirs(fdir, exist_ok=True)
for f in glob.glob(os.path.join(fdir, '*')):
    os.remove(f)

vf = 'fps=%g' % args.fps
if args.max_width:
    vf += ",scale='min(%d,iw)':-2" % args.max_width
cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-ss', args.start, '-t', str(args.dur),
       '-i', args.video, '-vf', vf, '-q:v', '2', os.path.join(fdir, '%04d.jpg')]
r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
frames = sorted(glob.glob(os.path.join(fdir, '*.jpg')))
say('抽帧 %s..%ss @%gfps → %d 帧（ffmpeg rc=%s）'
    % (args.start, args.dur, args.fps, len(frames), r.returncode))
if r.stderr.strip():
    say('  ffmpeg: %s' % r.stderr.strip()[:200])
if not frames:
    sys.exit('未抽到帧，检查 --start/--dur')

imgs = [(os.path.basename(f), M.imread_u(f)) for f in frames]
imgs = [(n, im) for n, im in imgs if im is not None]
say('分辨率 %dx%d' % (imgs[0][1].shape[1], imgs[0][1].shape[0]))

dev = get_cpu_device_info()
names = [s.strip() for s in args.detectors.split(',') if s.strip()]
raw = {}          # name -> {frame: frac or None}
secs = {}
for nm in names:
    try:
        det = DetectorFactory.create(nm, dev)
    except Exception as e:
        say('%-16s 加载失败 %s' % (nm, str(e)[:50]))
        continue
    t0 = time.time()
    d = {}
    for fname, im in imgs:
        try:
            boxes = norm_boxes(det.extract_with_kps(im) if hasattr(det, 'extract_with_kps')
                               else det.extract(im))
        except Exception:
            boxes = []
        if boxes:
            bb = max(boxes, key=lambda z: (z[2] - z[0]) * (z[3] - z[1]))
            d[fname] = (bb[2] - bb[0]) / float(im.shape[1])
        else:
            d[fname] = None
    raw[nm] = d
    secs[nm] = time.time() - t0

# 共识占比：各检测器最大框宽/图宽 的中位数
ref = {}
for fname, _ in imgs:
    vals = [raw[nm][fname] for nm in raw if raw[nm].get(fname) is not None]
    ref[fname] = float(np.median(vals)) if vals else None

BINS = [(0.0, 0.15, '远中景 <15%'), (0.15, 0.35, '近景 15-35%'), (0.35, 2.0, '特写 >35%')]
binframes = {l: [f for f, _ in imgs if ref[f] is not None and lo <= ref[f] < hi]
             for lo, hi, l in BINS}
say('')
say('参考占比分箱帧数：' + '，'.join('%s %d 帧' % (l, len(binframes[l])) for _, _, l in BINS))
say('')
say('%-16s %-9s %-10s %-38s %s' % ('检测器', '总检出', '占比中位', '分箱检出率（该箱内检出/该箱帧数）', '耗时/帧'))
say('-' * 104)
for nm in raw:
    d = raw[nm]
    hit = sum(1 for f, _ in imgs if d.get(f) is not None)
    med = np.median([v for v in d.values() if v is not None]) if any(v is not None for v in d.values()) else None
    cells = []
    for _, _, l in BINS:
        fr = binframes[l]
        h = sum(1 for f in fr if d.get(f) is not None)
        cells.append('%s %d/%d' % (l.split()[0], h, len(fr)))
    say('%-16s %-9s %-10s %-38s %s' % (
        nm, '%d/%d' % (hit, len(imgs)),
        ('%.0f%%' % (100 * med)) if med is not None else '—',
        ' / '.join(cells), '%.0f ms' % (1000 * secs[nm] / max(1, len(imgs)))))

say('')
say('漏检明细（参考占比 → 哪个检测器漏）：')
for fname, _ in imgs:
    miss = [nm for nm in raw if raw[nm].get(fname) is None]
    if miss:
        say('  %-10s 占比 %-6s 漏检: %s'
            % (fname, ('%.0f%%' % (100 * ref[fname])) if ref[fname] else '?', ', '.join(miss)))
if not any(raw[nm].get(f) is None for nm in raw for f, _ in imgs):
    say('  （本段无漏检）')

with open(os.path.join(HERE, 'video_segment_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(LOG))
say('')
say('报告: %s' % os.path.join(HERE, 'video_segment_report.txt'))
if not args.keep_frames:
    for f in glob.glob(os.path.join(fdir, '*')):
        os.remove(f)
    try:
        os.rmdir(fdir)
    except OSError:
        pass
    say('（临时帧已清理；需要保留加 --keep-frames）')
