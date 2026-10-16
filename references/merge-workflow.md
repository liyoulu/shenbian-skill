# 深变标准合成流程（作者设计，v4.0.9）

> 参考老 DFL 工作流的骨架，但深变的步骤更少：**视频直切脸（免切帧）→ 训练（或转换老模型）→ MergeStudio 网页合成 → 导出**。

## 流程总览（与老 DFL 对照）

| 阶段 | 老 DFL | 深变 | 说明 |
|---|---|---|---|
| ① 装载素材 | 硬链接到 workspace\data_dst.mp4 | 同左（视频直接放 workspace 根目录） | MergeStudio 扫 workspace 根目录的 .mp4/.mkv/.avi/.mov |
| ② 切帧 | 4) 切帧 BAT（ffmpeg 提 PNG） | **不需要**（除非要人工审查帧） | 深变 Extractor 视频直入，内部 ffmpeg 管道按帧解码 |
| ③ 切脸 | 5) 提取人脸 BAT | `Extractor\Extractor.py -i 视频 -o aligned目录` | 视频直接进；4K 建议 `-r` 预缩放提速 |
| ④ 清洗 | Sorter/手动 | FacesetProcessor（Filter/Sorter/Analyzer） | 4.0.8.3 起清晰度指标=高频/低频能量比，阈值自动定 |
| ⑤ 训练 | SAEHD BAT | `main.py train`（CLI）或 GUI 训练页 | 老模型可 `tools/convert_dfl_tf_to_torch.py` 转换续训 |
| ⑥ Merge | 7) 配置化交互Merge | **MergeStudio Web UI**（`python -m MergeStudio`，127.0.0.1:8000） | 免切帧：预览时 cv2 直接读视频帧 |
| ⑦ 合成输出 | 6) 合成 BAT（ffmpeg） | MergeStudio 内置导出（NVENC 硬件加速） | 4.0.7 起支持 GPU 解码加速 |
| ⑧ XSeg | XSeg 训练+应用 | XSegLite（快 4×）或 XSeg；DataAugmenter 批量应用 | 已有现成 onnx 可直接用 |


### 新 Extractor 默认/推荐参数（作者 GUI 默认值 = 官方推荐）

| 项 | 默认 | 说明 |
|---|---|---|
| 检测器 | **TinyMog** | 作者 tooltip「推荐：轻量高精度」；最高精度选 MogFace；对齐老流程习惯可换 S3FD。**实测另有一套更优解**（通用首选 YoloV8Face、远景 RetinaFace_10g、S3FD 慢约 20×）：见 [检测器与标记点选型](landmarker-selection.md) |
| 标记器 | **insightface-2d106det** | 唯一无警告；OpenSeeFace 仅 CPU，Google-mediapipe 左偏 |
| 检测模式 | One-Stage（快） | TinyMog/S3FD/RetinaFace/YOLO 适合 One-Stage；BlazeFace/MTCNN 适合滑窗 |
| 缩放 | LetterBox | 保比例；WarpAffine 最快但变形 |
| 输入尺寸 | 640 | 自动规整到 8 倍数 |
| KPS 对齐 | 开 | 检测器 5 点预旋转歪脸，仅 RetinaFace/DamoFD/TinyMog |
| HDR 模式 | 标准（满速） | HDR 精确模式 ~6fps，颜色完全正确 |
| 脸型/格式 | whole_face / jpg | 同老 DFL |
## 阶段②③：视频直切脸（核心差异）

老 DFL 必须先切帧再切脸；深变一步到位：

```powershell
Set-Location <DFL_ROOT>
.\python\python.exe Extractor\Extractor.py `
  -i "<视频目录>\...\<示例片>.mkv" `      # 视频直接进
  -o "workspace\data_dst\aligned" `          # 输出对齐人脸
  -d YoloV8Face -l insightface-2d106det `    # 检测器+标记器（S3FD 是老基准但慢约 20×，见 landmarker-selection.md）
  -t whole_face `                            # 脸型（默认 whole_face）
  -r 1280                                    # 4K 源预缩放宽度（提速，0=不缩）
```

关键参数：
- `-m video` 强制视频模式（auto 会自动识别）
- `--skip-frames N` 每 N+1 帧取 1 帧（快速试跑用；正式全量=0）
- `--quick-test` 只处理第一帧，验证参数
- `-a 0,90,180,270` 多角度（侧脸/倒置脸多时）
- 输出尺寸：`-s` 不传=按 bbox 动态（保质量）；训练需要统一尺寸时传固定值
- 检测模式 `--input-mode one_stage`（默认，大脸快）/ `sliding_window`（小脸多）
- `--resize-mode letterbox`（默认，保比例）/ `warp`（最快）

DST 目录结构（MergeStudio 依赖）：**视频 + 同名目录/aligned/**，即
```
workspace\<示例片>.mkv
workspace\<示例片>\aligned\*.jpg     ← _check_dfl() 按此识别 DFL 工程
```
切脸输出到 `workspace\<视频名>\aligned` 后，MergeStudio 打开 workspace 自动识别为 DFL 工程（detect_mode=skip_dfl，跳过内置检测直接用 aligned）。

## 切脸标准对照：训练素材 vs 临时 merge

> 目标不同 → 标准不同。**训练素材要"齐"（一致、干净、多样），临时 merge 要"全"（召回优先、能对齐就行）。**
> 同一批素材用两套参数各切一遍，是常见事故来源。

| 维度 | 训练素材（src/dst 脸集，喂模型） | 临时 merge（已有模型，只跑这一条片） |
|---|---|---|
| 目标 | 决定模型长期质量，脏数据进集就永久污染 | 只影响这条片的合成观感，可重跑 |
| 检测器 `-d` | 整片**固定一个**；src 多为大脸特写，`YoloV8Face`/`BlazeFace` 都行；dst 远景小脸多 → `RetinaFace_10g`（按素材调 `--input-size`） | 同样固定一个，但**更重召回**：漏一帧=该帧不换脸，成片断层；远景/侧脸多 → `RetinaFace_10g` + `-a 0,90,180,270`；赶时间可 `TinyMog`/`BlazeFace` |
| 标记器 `-l` | **整批固定一套**（取景/尺度必须一致，否则模型学到两套构图）：`2d106` 或侧脸多的素材用 `3DFAN-4` | 必须与**模型训练时的对齐口径一致**；同一片固定一套（侧脸多用 `3DFAN-4`） |
| 脸型 `-t` | **必须等于模型的 face_type**（whole_face 就整批 whole_face） | 同样是硬约束：脸型不匹配，合成必崩 |
| 输出尺寸 `-s` | **建议固定**（whole_face 用 512 等）：加载器虽会各自 resize，但动态尺寸会让同集内构图尺度抖动 | 可动态（省事），但与训练时一致最稳 |
| 覆盖/数量 | 够用即可：dst 几千～几万、src 上千；**多样性 > 数量** | **全片每一帧都要覆盖**（`--skip-frames 0`）：宁愿有几张歪的，不能漏帧 |
| 清洗 | **必做**：blur 剔糊、repeated 去重、faceid 拆身份（多人素材）、目检 | **不做/少做**：筛掉就是丢帧；只剔除极端错检（可在 MergeStudio 里逐帧跳过） |
| 多角度 `-a` | **慎用**：会把侧脸/倒置混进集，训练集以正脸为主时有害 | 侧脸/倒置镜头多时**必开** `0,90,180,270` |
| 预缩放 `-r` | 画质优先：4K 用原片慢跑，或接受代理帧的轻微损失 | 速度优先：`-r 1280` 无妨 |
| 遮罩 XSeg | 需要**遮罩集**（XSeg/XSegLite），dst 侧尤其 | 合成时用 `--xseg-onnx` 推理即可，**不需要预先切遮罩** |
| 一致性抽检 | 两边都要：点云/人脸框比落在 0.8–1.0、取景中心一致 | 同左，但可容忍个别异常帧 |
| 典型命令 | `-d YoloV8Face -l insightface-2d106det -t whole_face -s 512`（远景 dst 换 `RetinaFace_10g`） | `-d RetinaFace_10g -l 3DFAN-4 -t whole_face -a 0,90,180,270` |

出处：2026-09-30 实测（8 标记点 × 多尺度、15 检测器 × 43 用例）+ `references/landmarker-selection.md`。

## 阶段⑤：训练或老模型转换

### 模型格式速查（什么时候需要转换）

| 场景 | 需要转换吗 |
|---|---|
| 老 DFL .npy 模型在深变**续训** | 需要：convert_dfl_tf_to_torch.py（.npy→.pth，权重+优化器状态） |
| 老 DFL 生态**已有的 .dfm** 直接合成 | **不需要**：深变 MergeStudio 的 dfm 加载器就是标准 ONNX，与老 DFL exportdfm 产物完全兼容（<人物B>_SAEHD_model.dfm 已实测加载成功，320×320 签名一致） |
| 深变新训 .pth 模型要进 MergeStudio | 走 exportdfm 导出 dfm（深变正常流程，不算跨版本转换） |
| main.py merge CLI | **不需要 dfm**：与老流程一样直接加载 .pth 模型类交互合成（--pipeline 跳交互批量跑）。MergeStudio 与 CLI 是两个并列入口，不是新旧替代 |

> **现有模型清单 + 目录形态（junction 与否）见 [env-and-models.md](env-and-models.md)「模型盘点规程」**：深变只有 `<人物>`（.pth 可续训 / .dfm 可合成）；老工作流有 11 个身份 .npy + `<人物B>_SAEHD_model.dfm`。盘点时务必连顶层 .pth/.dfm 一起列，别只列子目录。

### 路线 A：老模型转换（仅续训时需要）

```powershell
# 把老 DFL 模型转成深变格式（复制不移动，原件不动）
.\python\python.exe tools\convert_dfl_tf_to_torch.py `
  --src "<老DFL-MVE安装根>\workspace\model" `
  --dst "<DFL_ROOT>\workspace\model" `
  --model SAEHD --name <人物>
```

- 支持 SAEHD/AMP/Quick96/XSeg，转换后可续训（权重+优化器状态都转）
- <人物> 是 df-udt 架构、416 分辨率、wf 脸型——转换器支持 df/liae 全架构
- 4.0.8.4 修了 LIAE 大 ae_dims（384）转换后权重错乱的 bug
- 转换后 DFM 导出（MergeStudio 可直接吃 DFM）：
  `.\python\python.exe main.py exportdfm --model-dir workspace\model --model SAEHD`

### 路线 B：GUI/CLI 直接训练

```powershell
# GUI：run.bat → 数据提取页（选检测器/标记器/参数）→ 训练页
# CLI：main.py train（参数走交互提示，默认值基本可用）
```

训练 WebUI：训练启动后浏览器开 127.0.0.1:6789（密码 caiji），看预览/loss/改参。

## 阶段⑥⑦：MergeStudio 合成

```powershell
.\python\python.exe -m MergeStudio    # 浏览器自动开 127.0.0.1:8000
```

Web UI 操作流：
1. **打开工程**：选 workspace 目录 → 自动扫到视频+模型+aligned
2. **选模型**：模型列表选 DFM（或 .pth/.npy 现场转 DFM）
3. **预览调参**（左侧参数面板，实时刷新）：
   - Seg mode：DFM（模型遮罩）/ XSeg / XSegLite
   - Mask mode：prd×dst（默认）/ prd / dst …
   - Color transfer：rct（默认）/ mt / lut / …
   - 滑条：erode/blur mask、face scale、super res、denoise 等
4. **时间线**：多轨道，不同片段不同参数（如某段遮挡多用 X-dst 遮罩）
5. **导出**：FFmpeg NVENC，4.0.7 起支持 GPU 解码加速

### HDR/10bit 源注意（<示例片> 是 4K 10bit）

- 切脸：标准 bt709 模式快；HDR 精确模式管道内 libplacebo 色调映射，颜色完全正确但慢
- 已切完的人脸可后补色调映射：`tools/tonemap_aligned_faces.py`
- MergeStudio 预览/导出基于 cv2 读视频，10bit 会按 8bit 处理——如色差明显，先用 ffmpeg 转 8bit bt709 再进流程

## 人工介入点（参考老工作流的两处）

1. 切脸后人工抽查 aligned 质量（老规矩）
2. MergeStudio 预览调参是流程的一部分（对应老流程的交互 Merge）
其余（装载、切脸、转换、导出）可自动执行。

## AV1 片源解码瓶颈（实测 2026-09-29，<示例片>）

- 4K AV1 10bit 软解只有 9.6-11 fps（OpenCV 默认不走硬件解码），切脸全管线被解码卡死，GPU 利用率仅 33%
- 提速方案：先转 H.264 代理再切——ffmpeg -hwaccel cuda -i in.mkv -c:v h264_nvenc -crf 18 proxy.mp4（32 分钟片约 5 分钟），之后切脸可到 25-40 fps，总时间减半以上
- 代价：脸图来自代理帧（8bit 转码），训练素材轻微质量损失——画质优先用原片慢跑，速度优先用代理
- 检测方法：ffprobe -show_entries stream=codec_name；纯解码基准（cv2 逐帧 read 120 帧计时）≈ 管线 fps 即确认解码瓶颈

### AV1 / 解码与切脸吞吐实测校准（2026-09-30，<示例片> 1080p AV1 10bit）

- **硬解能力是有的**：本机 ffmpeg 7.1.1 带 `av1_cuvid`（AV1 硬解）+ `cuda/d3d11va/dxva2/d3d12va`；
  MergeStudio 导出侧也有 `hwaccel` 参数（`export_pipeline.py` 的 `_hwaccel_for_encoder` / `_stage1_extract_frames(hwaccel=...)`）。
- **但 1080p 上硬解基本没收益**（前 60 秒原片实测）：

  | 方式 | fps |
  |---|---|
  | 软解 dav1d（默认） | **359 fps** |
  | 硬解 `-hwaccel cuda -c:v av1_cuvid` | **423 fps**（仅 +18%） |
  | 整条切脸管线（TinyMog + 2d106） | **~24 fps** |

  → 解码只占管线 **~7%**；上面那条"AV1 解码卡死"的记录是 **4K** 的实测（4K AV1 10bit 软解 9.6–11 fps），
  1080p 像素少 4 倍，压根不是瓶颈。**判据：先量 `ffmpeg ... -f null -` 的解码 fps，再决定要不要转代理/上硬解。**

- **1080p 每帧成本拆解**（41.7 ms/帧）：

  | 环节 | 耗时 | 占比 |
  |---|---|---|
  | 检测（TinyMog） | 17 ms | 41% |
  | 标记点（2d106） | 12 ms | 29% |
  | 解码（软解摊到每帧） | 2.8 ms | 7% |
  | 对齐 warp + JPEG 写盘 + metadata + Python 开销 | ~10 ms | 24% |

- **提速优先级（按实测收益）**：
  1. **标记点换 `PFLD`（1 ms/帧）**：省 ~11 ms/帧 → 约 32 fps（+25%）。真实片源基准里 PFLD 残差 0.055 与 2d106 同级、取景抖动最小，可放心换（见 landmarker-selection.md §九）。
  2. **先切帧再走 `-m image`**：Extractor 的 `-m image` 路径用 `ThreadPoolExecutor(cpu_count())` 并行，
     而**视频模式是串行的**（这是唯一的多线程入口）。用 ffmpeg 抽帧后跑 image 模式，值得实测。
  3. 换更快检测器：BlazeFace 只要 5–7 ms，但本片召回 53/60（TinyMog 60/60）→ 不建议为速度牺牲召回。
  4. 硬解：上限只有 ~7%，只在 4K 源或解码确实卡死时值得。
  5. `-r` 预缩放：1080p 无意义（检测才 17 ms），4K 才需要。

## 导出「取消后再也导不出来」死局 —— 根因与修复（2026-09-30 实机修复记录）

**症状**：在 MergeStudio 里取消一次导出后，再点导出什么都不发生，面板一直挂着 `❌ Export cancelled`（用户描述为「死局」）。

**三个叠加的 bug**（都不是玄学，逐一有证据）：

| # | 位置 | 问题 |
|---|---|---|
| 1 | `core/export_pipeline.py::_stage1_extract_frames` | 抽帧循环里**只 print 不调 `progress()`** → UI 全程停在 0%「Extracting frames」；加上 10bit AV1 硬解失败后**静默回退软解**，实际要几十分钟，看起来就是卡死 |
| 2 | `ui/js/export-flow.js::startExport` | 后端对已在跑的任务返回 400 `Export already running`，前端只有 `.then` 没有结果判断/`.catch` → **静默失败，界面毫无反应** |
| 3 | `ui/js/export-flow.js::_pollProgress` | 结束分支执行 `progress-label-0.parentElement.textContent = '❌ ' + msg`，**把整个进度层 DOM 覆盖掉**（进度条全消失），且下次启动不复位 → 旧提示永久挂着，看起来「无法导出」 |
| 4 | `api/routes_export.py` | 没有任何复位出口：工作线程死了但 `_running` 仍是 True 时，之后每次 start 都被 400 挡死，只能重启服务器 |

**修法**（改完要重启服务器才生效；JS 只需硬刷新浏览器）：

- `routes_export.py`：新增 `_export_thread` 线程句柄 + `_reset_export_state()`；
  `export_start` 发现 `running=True` 但线程已死 → **自动复位后继续**；`export_cancel` 线程已死 → 直接复位；
  新增 **`POST /api/export/reset`**（强制复位 + 杀残留 ffmpeg，UI 里对应「强制复位导出状态」按钮）。
- `export_pipeline.py`：新增 `CHILD_PROCS` / `register_child` / `unregister_child` / **`kill_children()`**（cancel/reset 能杀掉残留抽帧、编码进程）；
  `probe_frame_count()`（ffprobe JSON 取 `nb_frames`，缺字段回退 `duration×r_frame_rate`——**别用 `nk=1` 行解析，会把 duration 当帧数**）；
  抽帧循环按 `done/total` 回报进度；软解回退时在界面上提示。
- `ui/js/export-flow.js`：`startExport` 失败可诊断；**先探测旧任务是否还活着**——活着只提示（不误杀正在跑的导出），僵死才强制复位重试；
  `cancelExport` 等后端确认再关面板；进度面板改用独立状态行，不再覆盖 DOM；`_pollTimer` 统一管理，避免轮询泄漏。
- `ui/js/api.js`：新增 `resetExport()`。

**备份**：`<DFL_ROOT>\_fix_backup_20260930\merge_export_fix\`（4 个原文件 + 中途版本）。

**修复后实测**（60 帧小片）：启动 → 抽帧进度正常跳动（`Extracting frames 537/682`）→ 取消 3 秒内 `running=False` → **立刻再启动 HTTP 200 `status=started` 且任务继续推进** → reset 收尾干净。

**几个顺带实测到的坑**：
- **`cut_segments` 只裁剪抽帧之后的阶段**：抽帧永远整片抽完（`ffmpeg` 不带 `-frames:v`），所以「试 60 帧」也要先等全片抽完；试片段节省的是检测/换脸/编码时间。
- 抽帧速度：10bit AV1 + `-hwaccel cuda` 在真实内容上约 **50-60 fps**（20,448 帧 ≈ 6 分钟）；快片头/黑场段能到 200+ fps，用片头测速会严重高估。
- 重启服务器**必须带 APPDATA**（`set APPDATA=%APPDATA%` 或显式赋值），否则 `core/leras/device.py` 直接 `KeyError: 'APPDATA'`。
- 用 exec/脚本起服务器**不要在前台加重定向**（会一直挂着等子进程退出）→ 用后台启动。
- `workspace\.merge_auto.json` 记录上次的 workspace/model/video，重启自动恢复；指向已不存在的视频会让 `[AutoLoad] video select failed: 400`（不影响启动）。

## 常见陷阱（合成流程专用）

- **视频文件名**：workspace 里放一个视频即可；同名目录+aligned 触发 DFL 工程识别
- **老模型转换前先备份**：converter 是复制语义，但转换结果第一次要在小视频上验证
- **dfm 与 pth 可以并存**：exportdfm 生成 .dfm 后 MergeStudio 优先列 DFM
- **导出目录**：MergeStudio 导出写 workspace，完成后核对 result 文件
- **GPU 抢占**：训练时别同时跑 MergeStudio 导出（12GB 卡装不下两个大模型）
- **百度网盘 modelhub 包**：下载暂停是常态，检查客户端里是否要点继续/开加速
- **导出慢到离谱（0.2 it/s）＝ 显存被挤爆，不是模型问题**（2026-09-30 实测：RTX 3060 12GB / <示例片> 1080p）：
  导出面板 `workers` 留空＝自动＝`CPU核数//2`（本机 6 个换脸进程）→ 各带一份 ONNX session，显存逼近 **11.2/12.3 GB**
  → 换脸掉到 **0.2 it/s，20,448 帧全片约 19 小时**；改成 **workers=2** 后，300 帧试片（检测 300 帧 + 206 张脸换脸 + 合并）约 3.5 分钟走完，合并阶段 3.1 it/s。
  → **12GB 卡的导出 workers 填 2**，别留空；同理导出期间别同时训练。
- **cut_segments 是"保留"语义**（不是剪掉）：`[{start:0,end:299}]` = 只导前 300 帧；`[]` = 全片。试跑正好用它。
- **导出走 ffmpeg 抽帧**（`-pix_fmt rgb24`，`-hwaccel cuda` 失败会自动回落软解），跟预览用的 cv2 读帧不是一条路——
  10bit 源在**导出**环节由 ffmpeg 转换，色偏风险比预览小。
- **工作目录**：导出会在 `输出文件同目录\.export_<视频名>\` 下摊 frames/swap_pred/masks/export.db；正常结束或取消都会清掉，异常中断可能残留，看磁盘不对先查这里。

