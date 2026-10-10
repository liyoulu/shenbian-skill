# 零基础 Quickstart：一条命令链跑通深变

> 假设：深变已装好（`run.bat` 能开 GUI）。`<DFL_ROOT>` = 你的安装目录，下文所有命令都先 `Set-Location <DFL_ROOT>`，用深变自带 python（`.\python\python.exe`，下文简写 `python`）。
> 每一步都给了「照抄就能跑」的默认值；**什么时候才需要偏离默认**写在每步末尾。

## 0. 五分钟概念图

换脸 = 把 **src**（想换成的人的脸集）训进一个模型，再往 **dst**（目标视频）的每张脸上合成。所以流程永远是：准备 src 脸集 → 切 dst 的脸 → 清洗 → 训练 → 合成导出。src 和 dst 的脸都要经过「提取（检测+对齐）」这一步，产物叫 **aligned 脸集**（每张图内嵌 landmark 元数据）。

三个高频词：
- **检测器（-d）**：在整帧里框出人脸；**标记器（-l）**：在框里点 68 个 landmark 用于对齐。两者独立选型
- **face_type**：取景范围（half → full → whole → head），提取/训练/合成三处必须一致
- **XSeg**：遮罩模型，决定「换脸换到发际线还是下巴」；合成时用 XSeg-prd*XSeg-dst 通常最干净

## 1. 准备素材

**src（想换成谁）**：
- 数量：几千张起步（低于 1500 效果明显变差）；画面里只有这一个人
- 质量：分辨率 ≥ 训练分辨率（见 §4）、无大面积遮挡、清晰不糊
- 多样性：正脸/侧脸（±90°）、顺光/逆光/夜戏、表情丰富。角度覆盖比数量更重要
- 来源：图片文件夹直接喂；视频素材先用 `main.py videoed extract-video` 切成帧图再喂

**dst（换到哪部片）**：目标人脸清晰的视频文件（mp4/mkv/avi/mov），深变可以视频直入不用先切帧。
先看规格：`ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,bit_rate -of json <视频>`

什么时候偏离默认：4K/HDR 片源 → 提取时用 HDR 精确模式（颜色才正确）；素材有大量侧脸 → 标记器换 3DFAN-4。

## 2. 提取（切脸）

```powershell
# dst 视频 → aligned 脸集（近景大脸默认档）
python Extractor\Extractor.py -i "<DFL_ROOT>\workspace\data_dst.mp4" -o "<DFL_ROOT>\workspace\data_dst\aligned" -d YoloV8Face -l insightface-2d106det

# src 图片文件夹 → aligned 脸集
python Extractor\Extractor.py -i "<src图片目录>" -o "<DFL_ROOT>\workspace\data_src\aligned" -d YoloV8Face -l insightface-2d106det
```

先跑 `--quick-test`（只处理第一张图 + 调试图）确认参数没写错再放全量。常用补充参数：`-t whole_face`（取景，默认 full_face）、`-a 0,90,180,270`（检测旋转脸）、`-r 1920`（高分辨率源先预缩放提速）、`--skip-frames 1`（隔帧抽，快速过素材）。

切完自检：aligned 里应该绝大多数是同一张脸、取景一致。数字自检法（点云宽/人脸框宽 = 0.8–1.0）见 landmarker-selection.md。

## 3. 清洗

dst 脸集通常混了路人/配角，先拆身份再剔糊：

```powershell
python FacesetProcessor\Filter.py --input "<aligned目录>" --mode faceid --eps 0.3 --act report     # 先看聚类报告
python FacesetProcessor\Filter.py --input "<aligned目录>" --mode faceid --eps 0.3 --act split      # 按身份拆开
python FacesetProcessor\Filter.py --input "<主角身份目录>" --mode blur --act keep-best             # 剔模糊
```

（参数以 `python FacesetProcessor\Filter.py --help` 实际为准；原理与 GUI 对照见 data-processing.md。）
最后**目检**一遍 contact sheet——清洗是 GUI 少数值得用的环节。

## 4. 训练

```powershell
python main.py train --model-dir "<DFL_ROOT>\workspace\model" --training-data-src-dir "<DFL_ROOT>\workspace\data_src\aligned" --training-data-dst-dir "<DFL_ROOT>\workspace\data_dst\aligned" --model SAEHD --webui-port 6789
```

第一次启动会交互式问参数（对齐 iperov 习惯）。**新手默认档**：
- 架构 df（开头选）；分辨率 128 或 192 起步；face_type 与提取时一致（如 whole_face）
- batch_size 按显存（8GB→4~8；12GB→8~16）
- 新增强先全关（random_occlusion/noise/color 都 y→n 或 0），跑通后再按 new-params-guide.md 逐个开
- 想挂机看进度：浏览器开 127.0.0.1:6789（密码默认 caiji）

训到什么程度算够：预览里 src pred 侧已稳定、dst pred 侧细节跟得上（一般几万到几十万 iter，分辨率越高越久）。训练中别 kill 进程。

## 5. 合成（MergeStudio）

```powershell
python -m MergeStudio    # 浏览器自动开 http://127.0.0.1:8000
```

界面操作：项目区选 workspace 的视频/工程 → 左侧选模型 → 时间线调区间 → **预览区逐参数调** → 满意后导出。
**固定调参顺序**（一次只动一个滑块，每动一次看预览）：
1. mode 确认 overlay → 2. mask（mask_mode 选 XSeg-prd*XSeg-dst，没有 XSeg 就 learned-prd*learned-dst）→ 3. 边缘（erode_mask_modifier 内收/外扩、blur_mask_modifier 羽化）→ 4. 色彩（color_transfer_mode：rct 起步，偏色顽固换 mkl/lut）→ 5. 质感（super_resolution / denoise / motion_blur 按需）
每个滑块的含义与取值范围见 mergestudio-params.md。

## 6. 导出与验收

导出面板选 NVENC（硬编，快）或 libx264（兼容性最好）。大视频注意磁盘余量。
验收两条硬标准：① 抽 10 帧目检边缘与颜色；② 有条件做输出 vs 源帧的像素 diff（同帧同区域对比），确认脸真的换了而不是静默失败。

## 常见第一翻车点（按出现频率）

1. face_type 三处不一致（提取 whole_face、训练默认 full_face）→ 报错或取景错位
2. `-o` 用了相对路径，产物不知道去哪了 → 一律绝对路径
3. 训练选了 GPU 但实际在 CPU 跑（onnxruntime/torch CUDA 不配对）→ 训练前打印 provider 核实
4. B 站扫码弹窗卡住首启 → `SESSDATA=skip` 跳过
5. 显存不够 → 降 batch / 梯度检查点 / 降分辨率
6. 切脸检测器选错档（远景小脸用了 BlazeFace）→ 漏检严重，换 RetinaFace_10g/DamoFD 并调 `--input-size`
