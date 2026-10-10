# 环境基线与更新记录（低频参考，按需读）

## 版本矩阵（v4.0.9 实测参考）

| 组件 | 版本 | 验证命令 |
|---|---|---|
| Python | 3.12+（作者验证 3.12/3.14） | `python --version` |
| PyTorch | 2.9+（CUDA 12.6/12.8/13 均可，按官方安装） | `python -c "import torch;print(torch.__version__,torch.version.cuda)"` |
| onnxruntime | 与 torch 的 CUDA 版本配对（不匹配会静默退 CPU） | `python -c "import onnxruntime as o;print(o.__version__,o.get_available_providers())"` |
| ffmpeg | gyan.dev full 静态版（含 libplacebo，HDR 必需） | `ffmpeg -version` |

> 上游自 v4.0.7 起低维护模式（README 声明）：核心功能可用，新功能不再积极开发。参数面变化时应重校本 skill（跑 tools/doctor.py + tests/）。

## doctor 检查项说明

`tools/doctor.py` 检查：dfl_root（入口）/ modelhub_onnx（提取链路最小集 5 个 onnx）/ ffmpeg / cuda_provider / xseg_models（可选增强）/ disk_free（<20GB 警告）/ fork_extras（信息项：DFLPNG、chunked_export、3d68 补丁，上游版全 False 属正常）。退出码 0=全绿。

## 更新记录

- 2026-10-10（第二版）：面向 agent 优化——新增 doctor.py 环境自检与「第一动作」约定（先解析 DFL_ROOT 替换占位符、先跑 doctor）；marker_probe 三工具加 `--check`；frontmatter 补不适用反例（iperov 原版/DeepFaceLive/faceswap 等）；环境基线与更新记录下沉本文件（token 经济）；新增 tests/ 与 GitHub Actions CI
- 2026-10-10（首发）：基于个人版 shenbian skill 重构：剥离个人路径/实例，面向官方 v4.0.9 重写基准，新增 quickstart 与 mergestudio-params
