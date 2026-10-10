# -*- coding: utf-8 -*-
"""
标记点（-l）真实片源横向测试：取视频一小段 → ffmpeg 抽帧 → 检测器裁人脸 →
每个标记点在同一批人脸裁剪上跑一遍 → 出三类指标：

  ① 成功率：多少帧能给出有效的 68 点
  ② 形状共识残差：以全体标记点逐点中位数作共识，相似变换对齐后 RMS / 双眼间距
     （越小 = 越接近"主流"，也就是换了标记点后取景差异越小）
  ③ 取景一致性：用 get_transform_mat 对齐到 256 后，脸中心/尺度的跨帧波动（越小 = 脸集越整齐）
  另记每帧耗时（含预处理）。

用法：
  python video_landmarker_test.py --video "<视频>" [--start 00:01:10] `
      [--dur 10] [--fps 2] [--detector TinyMog] [--markers 全 8 个] [--keep-frames]

依赖同目录 mk_common.py（检测器/标记点推理、指标）。
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
    from facelib import LandmarksProcessor, FaceType

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(_env.ROOT, 'ffmpeg', 'ffmpeg.exe')
if not os.path.exists(FFMPEG):
    FFMPEG = 'ffmpeg'
ALL_MARKERS = ['insightface-2d106det', '2DFAN-4', '3DFAN-4', 'insightface-3d68',
               'Google-mediapipe', 'OpenSeeFace', 'PFLD', 'MobileFaceNet']
LOG = []


def say(s):
    print(s, flush=True)
    LOG.append(s)


def marker_runner(name):
    if name == 'insightface-2d106det':
        return M.run_2d106                 # 已含 106→68 映射
    if name == '2DFAN-4':
        return M.run_fan(2)
    if name == '3DFAN-4':
        return M.run_fan(3)
    if name == 'insightface-3d68':
        return M.run_3d68
    # 其余走各自封装。注意：这几个封装内部都已把坐标换算到裁剪像素（PFLD/MFN ×W,H；
    # OpenSeeFace /224×W,H；FaceMesh ×w_scale,h_scale），**不要再缩放**；FaceMesh 需要 468→68 映射。
    import importlib
    if name == 'Google-mediapipe':
        _fm = getattr(importlib.import_module('modelhub.onnx.FaceMesh.FaceMesh'), 'FaceMesh')
        from modelhub.onnx.FaceMesh.fm68_mapping import FM68_MAP
        inst = _fm(get_cpu_device_info())

        def f(crop):
            lm = np.asarray(inst.extract(crop), np.float64)      # (N,468,3) 裁剪像素
            return lm[0][FM68_MAP][:, :2]
        return f
    MOD = {'OpenSeeFace': ('modelhub.onnx.OpenSeeFace.OpenSeeFace', 'OpenSeeFace'),
           'PFLD': ('modelhub.onnx.PFLD.PFLD', 'PFLD'),
           'MobileFaceNet': ('modelhub.onnx.MobileFaceNet.MobileFaceNet', 'MobileFaceNet')}
    mp, cn = MOD[name]
    cls = getattr(importlib.import_module(mp), cn)
    inst = cls() if name == 'OpenSeeFace' else cls(get_cpu_device_info())

    def f(crop):
        return np.asarray(inst.extract(crop)[0], np.float64)
    return f


ap = argparse.ArgumentParser()
ap.add_argument('--video', required=False)
ap.add_argument('--check', action='store_true', help='环境自检后退出（不处理视频）')
ap.add_argument('--start', default='00:00:20')
ap.add_argument('--dur', type=float, default=10.0)
ap.add_argument('--fps', type=float, default=2.0)
ap.add_argument('--max-width', type=int, default=1920)
ap.add_argument('--detector', default='TinyMog')
ap.add_argument('--markers', default=','.join(ALL_MARKERS))
ap.add_argument('--frames-dir', default='', help='复用已抽好的帧目录（省一次 ffmpeg）')
ap.add_argument('--keep-frames', action='store_true')
args = ap.parse_args()
if getattr(args, 'check', False):
    import _env
    ok, lines_ = _env.selfcheck()
    print('\n'.join(lines_))
    sys.exit(0 if ok else 2)

if args.frames_dir and os.path.isdir(args.frames_dir):
    fdir = args.frames_dir
    say('复用帧目录 %s' % fdir)
else:
    if not os.path.exists(args.video):
        sys.exit('视频不存在: %s' % args.video)
    fdir = os.path.join(HERE, '_lframes')
    os.makedirs(fdir, exist_ok=True)
    for f in glob.glob(os.path.join(fdir, '*')):
        os.remove(f)
    vf = 'fps=%g' % args.fps
    if args.max_width:
        vf += ",scale='min(%d,iw)':-2" % args.max_width
    r = subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-ss', args.start,
                        '-t', str(args.dur), '-i', args.video, '-vf', vf, '-q:v', '2',
                        os.path.join(fdir, '%04d.jpg')], capture_output=True, text=True)
    say('抽帧 %s..%ss @%gfps（ffmpeg rc=%s）' % (args.start, args.dur, args.fps, r.returncode))

frames = sorted(glob.glob(os.path.join(fdir, '*.jpg')))
imgs = [(os.path.basename(f), M.imread_u(f)) for f in frames]
imgs = [(n, im) for n, im in imgs if im is not None]
if not imgs:
    sys.exit('未抽到帧')
say('帧数 %d，分辨率 %dx%d' % (len(imgs), imgs[0][1].shape[1], imgs[0][1].shape[0]))


def norm_boxes(raw):
    if raw is None:
        return []
    if isinstance(raw, np.ndarray):
        raw = [raw]
    if len(raw) > 0 and isinstance(raw[0], list) and len(np.asarray(raw[0]).shape) == 3:
        raw = raw[0]
    o = []
    for it in raw:
        if isinstance(it, (tuple, list)) and len(it) == 2 and np.asarray(it[0]).size == 4:
            o.append(np.asarray(it[0], np.float64).ravel())
        else:
            a = np.asarray(it, np.float64).ravel()
            if a.size >= 4:
                o.append(a[:4])
    return o


# ① 用检测器裁出人脸（同一批裁剪喂所有标记点，与 Extractor 做法一致）
dev = get_cpu_device_info()
det = DetectorFactory.create(args.detector, dev)
crops, miss = [], []
for fname, im in imgs:
    try:
        bs = norm_boxes(det.extract_with_kps(im) if hasattr(det, 'extract_with_kps')
                        else det.extract(im))
    except Exception:
        bs = []
    if not bs:
        miss.append(fname)
        continue
    bb = max(bs, key=lambda z: (z[2] - z[0]) * (z[3] - z[1]))
    H, W = im.shape[:2]
    half = int(max(bb[2] - bb[0], bb[3] - bb[1]) * 0.5 * 1.4)
    cx, cy = int((bb[0] + bb[2]) / 2), int((bb[1] + bb[3]) / 2)
    c = im[max(0, cy - half):cy + half, max(0, cx - half):cx + half]
    if c.shape[0] >= 120 and c.shape[1] >= 120:
        crops.append((fname, c))
say('检测器 %s 裁出 %d/%d 张人脸%s' % (args.detector, len(crops), len(imgs),
                                      ('（漏 %s）' % ','.join(miss[:6])) if miss else ''))

names = [s.strip() for s in args.markers.split(',') if s.strip()]
res = {}     # marker -> {frame: pts or None}
speed = {}
for nm in names:
    try:
        fn = marker_runner(nm)
        t0 = time.time()
        d = {}
        for fname, c in crops:
            try:
                pts = np.asarray(fn(c), np.float64)
                d[fname] = pts if (pts.ndim == 2 and pts.shape[0] >= 68 and np.isfinite(pts).all()) else None
            except Exception:
                d[fname] = None
        speed[nm] = time.time() - t0
        res[nm] = d
    except Exception as e:
        say('%-22s 加载失败 %s' % (nm, str(e)[:60]))

# ② 形状共识残差
say('')
say('%-22s %-9s %-12s %-30s %s' % ('标记点', '成功', '共识残差', '取景中心(256框内)±std', '耗时/帧'))
say('-' * 100)
summary = {}
for nm in res:
    d = res[nm]
    ok = [f for f, _ in crops if d.get(f) is not None]
    errs, cxs, cys, szs = [], [], [], []
    for fname, c in crops:
        p = d.get(fname)
        if p is None:
            continue
        mat = LandmarksProcessor.get_transform_mat(p, 256, FaceType.WHOLE_FACE)
        al = LandmarksProcessor.transform_points(p, mat)
        sub = al[17:68]
        cxs.append(sub[:, 0].mean()); cys.append(sub[:, 1].mean())
        szs.append(np.linalg.norm(sub[:, 0].max() - sub[:, 0].min()))
        others = [res[k][fname][:64] for k in res if k != nm and res[k].get(fname) is not None]
        if len(others) >= 2:
            cons = np.median(np.stack(others), axis=0)
            errs.append(M.rms_iod(p[:64], cons))
    med_err = np.median(errs) if errs else float('nan')
    summary[nm] = dict(ok=len(ok), total=len(crops), err=med_err,
                       cx=np.median(cxs) if cxs else -1, cy=np.median(cys) if cys else -1,
                       cxstd=np.std(cxs) if cxs else -1, cystd=np.std(cys) if cys else -1,
                       szstd=np.std(szs) / 256.0 * 100 if szs else -1)
    say('%-22s %-9s %-12s %-30s %s' % (
        nm, '%d/%d' % (len(ok), len(crops)),
        ('%.4f' % med_err) if errs else '—',
        ('(%.1f,%.1f) ±(%.2f,%.2f)' % (summary[nm]['cx'], summary[nm]['cy'],
                                       summary[nm]['cxstd'], summary[nm]['cystd'])) if cxs else '—',
        '%.0f ms' % (1000 * speed.get(nm, 0) / max(1, len(crops)))))

say('')
say('登记失败帧（谁在哪些帧给不出有效点）：')
for nm in res:
    bad = [f for f, _ in crops if res[nm].get(f) is None]
    if bad:
        say('  %-22s %d 帧: %s' % (nm, len(bad), ', '.join(bad[:10])))

with open(os.path.join(HERE, 'video_landmarker_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(LOG))
say('')
say('报告: %s' % os.path.join(HERE, 'video_landmarker_report.txt'))
if not args.keep_frames and not args.frames_dir:
    for f in glob.glob(os.path.join(fdir, '*')):
        os.remove(f)
    try:
        os.rmdir(fdir)
    except OSError:
        pass
    say('（临时帧已清理；--keep-frames 保留）')
