# MergeStudio 合成参数文档（滑块全家桶）

> 依据：`MergeStudio/core/config.py` 的 `MergerConfigMasked` + merger.py 实跑（v4.0.9）。
> Web UI 里每个滑块对应下面一个字段；本文按「你会遇到的问题」组织。

## mode（合成模式，8 档）

| 值 | 名字 | 干什么 |
|---|---|---|
| 0 | original | 原帧不动（对照用） |
| 1 | **overlay** | 标准合成，**默认从这里开始** |
| 2 | hist-match | 直方图匹配后再合成（颜色贴近 dst） |
| 3 | seamless | 泊松融合（边界自然但会糊/变色） |
| 4 | seamless-hist-match | 3+2 组合 |
| 5 | raw-rgb / 6 | raw-predict | 调试用：看模型原始输出 |
| 7 | debug | 调试信息 |

新手路径：overlay → 边缘有硬边就试 seamless-hist-match（更慢）。

## mask_mode（遮罩模式，10 档）——决定换脸范围

| 值 | 名字 | 说明 |
|---|---|---|
| 0 | full | 整个 aligned 取景都换（含背景，最假） |
| 1 | dst | 用 dst 自己的形状遮罩 |
| 2/3 | learned-prd / learned-dst | 模型预测的遮罩 |
| 4 | learned-prd*learned-dst | 两者交集，**无 XSeg 时的默认** |
| 5 | learned-prd+learned-dst | 两者并集 |
| 6/7 | XSeg-prd / XSeg-dst | XSeg 遮罩（推荐先装 workspace/model/XSeg 的官方 onnx） |
| **8** | **XSeg-prd*XSeg-dst** | XSeg 交集，**大多数片子的最优解** |
| 9 | learned*learned*XSeg*XSeg | 四重交集，极限收边 |

seg_mode='model' 表示用模型算遮罩；另有手动/多边形选项（GUI 标注）。

## 边缘三兄弟

- **erode_mask_modifier**（负=内收，正=外扩）：换脸区域收缩/扩张。边缘露出原脸 → 负方向收；XSeg 遮罩太紧切到五官 → 正方向放
- **blur_mask_modifier**（羽化，越大越软）：边缘硬 → 加大到 40–80；糊成一团 → 减
- **output_face_scale**（输出脸整体缩放，-x%~+x%）：换上去的脸比原脸大一圈/小一圈时微调

## 色彩 color_transfer_mode（ctm，11 档）

| 值 | 名 | 一句话 |
|---|---|---|
| 0 | None | 不调色 |
| 1 | **rct** | Reinhard 均值/方差匹配，**起步默认**（v4.0.9 起在去相关空间 Y/R-Y/B-Y 做，更稳） |
| 2 | lct | 线性匹配 |
| 3/4 | mkl / mkl-m | Mongi-Khoudir-Larabi；-m 为遮罩版本 |
| 5/6 | idt / idt-m | 迭代分布迁移 |
| 7 | sot-m | 遮罩加权 SOT |
| 8 | mix-m | 混合 |
| 9 | **mt** | 本项目新增：遮罩**软加权**均值/方差（正确使用羽化遮罩，RGB 空间） |
| 10 | **lut** | 本项目新增：SOT 对应 + 17³ 3D LUT 最小二乘拟合，有界非线性，适合顽固偏色 |

调色顺序建议：rct → 还偏就 mkl/lct → 再顽固上 lut。hist_match_threshold（hist-match 模式下 0–255，默认 238）控制直方图匹配的截断。

## 质感与修复

- **super_resolution_power**（0–100）：FaceEnhancer 超分，脸糊时加；过高会「假锐」
- **image_denoise_power**（0–500）：降噪，噪点明显时加
- **bicubic_degrade_power / color_degrade_power**：反向降质——让换上的脸**匹配 dst 的烂画质**（老片/高 ISO 夜戏神器）
- **motion_blur_power**（0–100）：给静态预测脸补动态模糊，匹配快速运镜
- **sharpen_mode / blursharpen_amount**：锐化（blur-sharpen 族）

## 交互与导出

- **masked_hist_match**（默认开）：hist-match 只在遮罩内统计
- **show_debug**：预览显示遮罩/中间量，排障用
- 导出：NVENC（硬编快）或 libx264；帧缓冲盘建议 SSD（小文件密集 IO）
- **face_type**：合成时的取景，必须与提取/训练一致
- FaceAvatar 模式（temporal_face_count）：时序脸替换，多帧联合推理降抖动，适合慢镜头

## 固定调参顺序（背下来）

**mask（mode 8）→ 边缘（erode/blur）→ 色彩（ctm）→ 质感（超分/降噪/降质/动态模糊）**，一次一个滑块，每动看预览。颜色永远在遮罩调好之后调，否则白调。
