---
name: shenbian
description: 深变（DeepFaceLab-PyTorch / DeepFaceLab-Torch）工作流 skill：装好深变之后，从素材准备、切脸（15 检测器/8 标记器）、数据清洗、训练（SAEHD/LIAELarge/AMP/XSeg 等）、XSeg 遮罩、MergeStudio 网页合成到导出的全流程实操手册。含实测选型数据、常见任务 SOP、参数文档与排障。适用于官方版 v4.0.9（github.com/CaijiPlayer258/DeepFaceLab-PyTorch）。说"深变"、"DFL-PyTorch"、"DFL-Torch"、"MergeStudio"时用本 skill；不适用：原版 iperov DeepFaceLab（TF 版）、"老版/C 盘版/老工作流"、DeepFaceLive、faceswap/roop 等其它工具。
---

# 深变（DeepFaceLab-PyTorch）公共版工作流 skill

> 目标读者：装好深变、想尽快跑通「视频进 → 成片出」的用户，以及替用户操作深变的 AI agent。
> 上游：https://github.com/CaijiPlayer258/DeepFaceLab-PyTorch （B 站 @菜级玩家）
> 本 skill 基于官方 v4.0.9 实测整理（2026-09/10），README 官方文档 + 源码 + 实跑交叉验证。

## ⚡ 第一动作（agent 激活本 skill 后先做这两件事）

1. **解析 DFL_ROOT 并替换全文占位符**：本文件与所有 references 中命令里的 `<DFL_ROOT>` 一律先替换为真实路径再执行。解析顺序：环境变量 `DFL_ROOT` → 自动探测（`tools\marker_probe\_env.py` 的逻辑：F:/C:/D:/`~/` 下的 DFL-PyTorch 且含 main.py）。
2. **跑环境自检**：`python <skill目录>\tools\doctor.py`（退出码 0 才继续正式工作；非 0 时按输出里的 fix 提示处理，或向用户报告）。marker_probe 工具另有单工具版 `--check`。

## 你需要先有

1. 深变已安装可跑（含 modelhub/onnx 模型包、ffmpeg、python 环境）——安装见上游 README
2. 一张 NVIDIA GPU（8GB+ 推荐；显存不够的参数见 new-params-guide.md）
3. 本 skill 假设安装根目录为 `<DFL_ROOT>`（下文用这个占位符；脚本通过环境变量 `DFL_ROOT` 自动探测，也可自动探测 F:/C:/D: 盘常见位置）

## 全流程总览（六步）

```
① 收集素材 ──► ② 提取切脸 ──► ③ 清洗脸集 ──► ④ 训练 ──► ⑤ MergeStudio 合成 ──► ⑥ 导出
 src/dst 选材    视频直入       拆身份/剔糊    SAEHD 等     Web UI 调参          mp4
```

| 阶段 | 入口 | 新手 30 秒决策 |
|---|---|---|
| ① 素材 | 自备 | src 脸集多角度多光照、dst 视频目标人脸清晰；详见 quickstart.md |
| ② 提取 | `Extractor\Extractor.py` | 近景大脸 YoloV8Face；远景小脸 RetinaFace_10g；标记点默认 insightface-2d106det，侧脸多改 3DFAN-4 |
| ③ 清洗 | `FacesetProcessor\Filter.py` / `Sorter.py` | faceid 拆身份 + blur 剔糊，见 data-processing.md |
| ④ 训练 | `main.py train` | 新手 SAEHD + df 架构；新手默认档见 quickstart.md §4 |
| ⑤ 合成 | `python -m MergeStudio` | 端口 8000；调参顺序见 mergestudio-params.md 的「固定调参顺序」 |
| ⑥ 导出 | MergeStudio 导出面板 | NVENC 硬编；大视频（≥2K/≥50fps）注意磁盘占用 |

## 模块路由

| 你想做什么 | 去处 |
|---|---|
| 零基础第一次跑通全流程 | [quickstart.md](references/quickstart.md) |
| 准备切脸、选 `-d`/`-l`/`-t`/`-s`/`-a` 参数 | [landmarker-selection.md](references/landmarker-selection.md) §0 速查 |
| 切脸结果一部分好一部分坏、自查 | 同上（云/框比 0.8–1.0 自检法 + tools/marker_probe/） |
| 脸集筛选/分组/清洗 | [data-processing.md](references/data-processing.md) |
| 问训练参数（新增强/新损失/lr/冻结/预训练/模型类型） | [new-params-guide.md](references/new-params-guide.md) |
| 问合成滑块（mode/mask/erode/blur/超分/调色…） | [mergestudio-params.md](references/mergestudio-params.md) |
| 端到端流程细节与老 DFL 差异 | [merge-workflow.md](references/merge-workflow.md) |
| 遇到报错/异常 | 本文件「排障速查」 |

## 常见任务 SOP

**SOP-1 新视频全流程**
ffprobe 看规格 → 切脸（--quick-test 先验参数）→ 清洗 → 训练（或用现成模型）→ MergeStudio 合成导出 → 抽帧目检 + 像素 diff 审计（不要只看导出成功与否）。逐步命令见 quickstart.md。

**SOP-2 换 dst 素材续训**
确认无训练进程在跑 → data.dat 会提示重置，按提示确认（权重保留）→ 新素材切脸清洗 → `main.py train` 续训。训练中禁止 kill 进程；状态只看 GPU 利用率。

**SOP-3 老 DFL（TF）模型转来用**
`tools\convert_dfl_tf_to_torch.py`（权重+optimizer state 无损转换）+ `tools\verify_converted_dfl_model.py`（建议 --deep 校验）。老 DFL 生态的 .dfm 也可直接给 MergeStudio 加载（标准 ONNX，实测兼容）。

**SOP-4 DFM 导出与 DeepFaceLive**
`main.py exportdfm --model-dir <目录> --model <类型>`；官方工具 `tools\export_dfm.py`。AMP 架构导出的 DFM 是双输入（morph_value），给 DeepFaceLive 用注意喂 1.0。

**SOP-5 排障速查**
1. onnx 静默退 CPU → 打印 provider 核实（`onnxruntime.get_available_providers()`）；后台/子进程启动补 APPDATA/LOCALAPPDATA 环境变量
2. 切脸「一部分好一部分坏」→ 云/框比自检 0.8–1.0（landmarker-selection.md）
3. 改了 .py 不生效 → 重启 GUI/MergeStudio（模块不热更新）
4. 显存不足 → 降 batch / 开梯度检查点 / BF16（new-params-guide.md）
5. MergeStudio 端口占用 → 启动脚本会提示处理
6. HDR 颜色不对 → 提取时选「HDR 精确模式」（libplacebo 管道内色调映射）
7. 长任务请用独立进程跑（`Start-Process -PassThru` + 日志重定向），不要在交互会话里前台等待

## 环境基线与更新记录

版本矩阵（Python/PyTorch/onnxruntime/ffmpeg）、验证命令、更新历史见 [meta.md](references/meta.md)。上游自 v4.0.7 起低维护模式：核心功能可用，新功能不再积极开发。

## 常见陷阱（浓缩版）

- 切脸 `-o` 输出用**绝对路径**；同一部素材固定一套 `-d`/`-l`，混用会取景/尺寸不统一
- face_type 链：提取 `-t` → 训练 face_type → 合成 face_type **必须一致**（提取用 whole_face、训练默认 full_face 是新手第一大坑）
- `ULFD`/`LightweightFD` 检测器框约定有问题，别用
- 首次 GUI 启动会弹 B 站扫码登录（解锁 B 站下载器 + 自动关注作者账号）；不需要就往 `ui/user/bilibili_cookie.txt` 写 `SESSDATA=skip` 跳过，不影响核心功能
- modelhub/onnx 里**没有 XSeg**：XSeg/XSegLite 属于项目模型，从 HuggingFace 下载后放 `workspace/model/XSeg/`、`workspace/model/XSegLite/`（链接见 README）
- 模型盘点别只列子目录——深变模型是 model 目录**顶层文件**（.pth/.dfm）
- webui 训练密码默认 caiji（`--webui-password` 可改）

## 实测数据与工具

- `tools/doctor.py`：环境自检（根目录/modelhub/ffmpeg/CUDA provider/XSeg/磁盘/fork 增强；`--quiet` `--json` 可选）——**agent 每次激活先跑它**
- `tools/marker_probe/`：检测器/标记点实测装置（video_segment_test / video_landmarker_test / make_contact_sheet + mk_common/_env 库，均支持 `--check` 自检）。运行前置：`DFL_ROOT` 环境变量或自动探测
- 实测结论全部在 references（选型表、阈值、性能数字），均可复跑

## 更新记录

见 [meta.md](references/meta.md)。
