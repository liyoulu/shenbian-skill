# 深变独有参数深度说明

> 范围：只解释老 DFL（iperov 原版）没有的参数。lr / gan_power / face_style_power / random_warp / ct_mode 等老参数不在此重复。
> 依据：仓库源码（Model_pytorch.py / ModelBase.py / merger.py / params.js）+ 作者 updata.txt changelog，v4.0.0–4.0.9。

## 一、训练新参数（按功能分组）

### 1. 数据增强组（2026-09-29 v4.0.9 新增，互不影响，作用顺序：噪点 → 遮挡 → warp → 偏色）

| 参数 | 选项/范围 | 机制 | 建议用法 |
|---|---|---|---|
| random_noise 随机噪点 | y/n | 加噪点+轻微偏色，**作用在 warp 和遮挡之前**。目的：输入有噪时模型不重建出偏色人脸 | dst 视频画质差（老片、夜戏、高 ISO）时开；干净素材不用 |
| random_occlusion 随机遮挡 | y/n | 随机数量/大小的黑色方块，**作用在 warp 之前**。目的：学会从遮挡处重建（手、话筒、头发遮脸） | dst 常有遮挡物时开；与噪点互不影响，可同开 |
| random_color_power 随机偏色强度 | 0.0–1.0 | 给输入加异色光照：原图 A 偏色得 C，其余增强作用在 C 上得 W；模型喂 W，loss 比较 CT(pred, C)。**目标永远是干净原图 A** | 光照多变（舞台、霓虹、夜戏）时 0.3 左右起试；默认 0 关闭 |
| random_color_alg 随机偏色算法 | none/rct/lct/mt/direct | loss 侧色彩迁移方法。none=整个功能关闭；**direct=不做色彩迁移，强制模型输出正常光照**（最强约束）；rct/lct/mt=loss 里先把 pred 迁到目标色再比较（色彩中性化，不强迫光照） | 想纠偏色用 direct；只想增稳用 rct/mt |

**对比**：噪点/遮挡是"污染输入逼模型鲁棒"；偏色是"异色光照下仍重建干净原图"。三者作用在不同环节，可叠加。老 DFL 只有 random_warp + random_hsv，没有这三件套。

### 2. 损失函数组

| 参数 | 范围 | 机制 | 建议 |
|---|---|---|---|
| edge_enhance_power 边缘强化 | 0.0–20.0 | 把预测脸用**模型自己的遮罩**合成回原图再算 loss，误差按 m·(pred−tgt) 加权，**专罚过渡带（0<mask<1）**——这正是合成后人脸边缘硬边的来源 | 合成边缘有硬边/色差圈时 1.0–5.0 起试；默认 0 |
| vgg_perceptual_power VGG 感知损失 | 0.0–100.0 | VGG16 特征 L1 损失提升自然纹理。50=与重建损失各半；v4.0.6 起默认 0（作者实测收益不稳） | 皮肤纹理塑料感重时小值（10–25）试；默认 0 即可 |
| morph_factor 形变系数（仅 AMP 模型） | 0.1–0.5 | src/dst inter 编码按二项式 shuffle 混合的比例，AMP 模型特有 | 常用 0.5 |

### 3. 学习率策略组（v4.0.8 新增）

| 参数 | 范围 | 机制 | 建议 |
|---|---|---|---|
| lr_plateau_factor 平台期自动降 lr | 0.1–0.9（1.0=关） | 连续 N 步 loss 无实质改善→lr×factor。**不需要预知总步数**，patience=0 自动定 patience，min_ratio=0.1 保底 | 一直挂着训的场景用它；作者推荐的正确降 lr 方式 |
| lr_plateau_patience 耐心步数 | 0=自动 | 多少步无改善算平台 | 默认自动即可 |
| lr_plateau_min_ratio lr 下限 | 0.01–0.5 | lr 衰减到初始值这个比例后不再降 | 默认 0.1 |
| lr_cos 余弦退火·热重启 | 0=关，>0=周期 | ⚠️ **这是 SGDR 热重启，不是单调退火**：每 N 步 lr 弹回峰值重开一轮。作者实测后期反复踢出收敛极小值，质量更差 | **保持 0**。想要单调下降→用平台期降 lr；4.0.8 起 lr_cos 与 lr_dropout 解耦 |

### 4. 冻结组（DeepFakeLarge / LIAELarge 模型）

| 参数 | 机制 | 建议 |
|---|---|---|
| freeze_encoder 冻结编码器 | encoder 不再更新 | 已收敛模型微调时保护通用特征 |
| freeze_bottleneck 冻结瓶颈层 | bottleneck（inter 层）不更新 | 同上 |
| freeze_decoderB 冻结 dst 解码器 | **整个 dst 解码器不参与训练**（前向都跳过），dst 侧 warp/遮挡/噪点/HSV 自动关闭，**偏色保留**（它同时充当 dst 的输入与目标）。仅 DF 架构 | src 身份已稳、只想让 dst 侧更干净时；SAEHD 里叫 freeze_decoder_dst（4.0.4+），与 encoder/inter 联动一起冻结 |
| freeze_decoderA_mask / freeze_decoderB_mask | 分别冻结解码器 A（src/dst 交叉用）和 B（dst 重建用）的 mask 分支（4.0.6 拆分成两个，旧 freeze_decoder_mask 自动映射到两个都开） | mask 分支已收敛但颜色还在变时 |

### 5. 显存/速度组

| 参数 | 机制 | 建议 |
|---|---|---|
| gradient_checkpointing 梯度检查点 | 用约 30% 额外计算换显存。**显存不够时开** | 12GB 卡训练 256+ 分辨率大模型 OOM 时开 |
| use_fast_generator 快速生成器 | 多进程预取加载器（V4/V2 生成器），显著提升数据加载速度 | 实验性：加载慢（GPU 利用率低、数据等待）时开，出样本异常就关 |
| use_bf16 BF16 混合精度 | 默认开启。RTX 30 系（Ampere+）支持 | 30 系保持默认开；老卡（10/16 系）关 |
| optimizer 优化器 | adam=标准省显存；adabelief=精度/泛化更好但费显存；**lion**=Google 2023，省显存适合大模型 | 12GB 卡大模型选 lion；一般 adam/adabelief |
| crash_threshold 崩溃检测器 | loss 突跳超阈值（默认 4.0）自动回滚到最近备份，防模型崩溃白训 | 默认 4.0；误报（合理大波动被回滚）时调大 |
| backup_interval / max_backups | 备份间隔迭代数 / 最大备份数 | 默认 500 / 24 |

### 6. 预训练组

| 参数 | 机制 | 建议 |
|---|---|---|
| pretrain 预训练开关 | SAEHD 的 TF 版 pretrain 已停用（强制 False）；PyTorch 版重做：src/dst 都用 pretraining 数据集（多身份脸集）训练编码器。**预训练集不限格式**：faceset.pak 打包目录或散装 DFLJPG 对齐目录都行（SampleLoader 自动识别；指到 .pak 文件本身会自动改用其所在目录） | 通常直接用现成预训练模型；要自训预训练模型时，多身份脸集收益最高，单身份 dst 也能跑但收益打折 |
| pretrain_single_decoder 预训练单解码器 | 预训练只跑 src 支路（encoder+inter+decoder_src），保存时权重同步给 decoder_dst。两支路同分布效果一致，省一条支路的显存/优化器状态。仅 DF 架构 | 预训练时开，可上更大 batch |

### 7. 预览组

| 参数 | 机制 | 建议 |
|---|---|---|
| preview_grade_alg 合并预览调色 | 「合并预览」行第 5 列用的调色算法，**独立于 ct_mode**（4.0.9 之前预览写死 RCT 且与合并行不一致的 bug 已修）。same=跟随 ct_mode；lut/mt 等指定算法 | 纯预览设置：想在预览里看不同调色效果又不动训练时用 |

## 二、切脸新参数（Extractor/）

| 参数 | 说明 |
|---|---|
| -d/--FaceDetector | 14 种检测器：BlazeFace（最快）/ CenterFace / S3FD（老 DFL 同款精度基准）/ RetinaFace / MTCNN / YoloV5Face / YoloV8Face / YoloV11nFace / MogFace / TinyMog / ULFD / DamoFD / LightweightFD / FastFaceAlign（4.0.4 新增）。无 = 跳过检测 |
| -l/--FaceMarker | **8 种标记器**：insightface-2d106det（默认首选，快+准）/ 2DFAN-4 / 3DFAN-4（老 DFL 同款，侧脸最稳）/ insightface-3d68（唯一带 z，量纲需修复）/ Google-mediapipe / OpenSeeFace（解码有系统性平移，慎用）/ PFLD / MobileFaceNet。选型与实测数据见 [标记点选型](landmarker-selection.md) |
| -a/--angles 多角度检测 | 图像旋转 0/90/180/270° 分别检测再 IoU 去重，坐标自动转回。侧脸、倒置脸召回率大增 |
| --test 快速测试 | 只处理第一张图出全流程可视化，验证参数配置 |
| --size 动态尺寸 | 不传时按人脸 bbox 自动算输出尺寸（保留原始质量）；传固定值则统一尺寸（训练需要统一） |
| 预缩放 | 4K+ 源先预缩放再检测，速度大幅提升 |
| bt709 标准模式 / HDR 精确模式 | 标准模式快速直出（HDR 源后处理色调映射可补：tools/tonemap_aligned_faces.py）；HDR 模式管道内 libplacebo 色调映射，4K 直出颜色完全正确但慢 |
| Sliding Window / One-Stage | 4.0.2 新增检测模式：滑窗（小脸多）vs 单阶段（大脸快）；One-Stage 自动跳过预缩放 |
| LetterBox / WarpAffine | 4.0.2 缩放方式选择 |

## 三、合成新参数（MergeStudio / merge CLI）

### Seg mode 遮罩来源（seg_mode，UI 按钮 DFM/XSeg/XSegLite）

- **model（DFM）**：用换脸模型自己输出的遮罩（默认）
- **xseg / xseglite**：用 XSeg/XSegLite ONNX 模型的遮罩**替换**模型遮罩（对所有 mask_mode 生效，config 里可选，CLI 是 `--xseg-onnx` + `--xseg-onnx-res`，res 推荐 256）

### Mask mode 遮罩模式（mask_mode 0–9，UI 显示 prd×dst / prd / dst 三档，全量在 CLI）

| 值 | 组合 | 说明 |
|---|---|---|
| 0 | full | 整脸全遮罩 |
| 1 | dst | dst hull 遮罩（老 DFL 同款） |
| 2 | learned-prd | 模型预测遮罩 |
| 3 | learned-dst | 模型预测的 dst 侧遮罩 |
| 4 | prd×dst | **默认**。两者相乘，最常用 |
| 5 | prd+dst | 两者相加取 clip |
| 6 | X-prd | XSeg 对预测脸的遮罩 |
| 7 | X-dst | XSeg 对 dst 脸的遮罩 |
| 8 | X-prd×X-dst | 两个 XSeg 遮罩相乘 |
| 9 | 全乘 | learned-prd × learned-dst × X-prd × X-dst，最严格 |

### Color transfer 色彩迁移（UI: rct / mt / lut / lct / mkl / idt / sot-m / mix-m / none）

| 模式 | 机制 | 优劣 |
|---|---|---|
| rct | Reinhard，**4.0.9 起在去相关空间（Y/R-Y/B-Y）匹配**——缩放单通道不再扭曲色相饱和度；且修了遮罩统计被稀释的 bug（脸部覆盖率 17.6% 时 offset 0.0632→0.0009） | 默认首选，快而稳 |
| **mt**（新） | 遮罩软加权均值/方差，原生 RGB 空间 sum(x·m)/sum(m)。**正确使用羽化遮罩**，不再依赖 mask_cutoff 硬阈值 | 羽化遮罩场景比 rct 更准；4.0.9 同步进训练预览与合成链路 |
| **lut**（新） | SOT 求像素级对应 → 最小二乘拟合 17³ 3D LUT（拉普拉斯平滑+单位先验，稀疏 CG）→ 三线性查表。有界、非线性、确定性 | 色差复杂（非线性色偏）时最强；计算比 mt 慢 |
| lct / mkl / idt / sot-m / mix-m | 老 DFL 已有的线性/ MKL / IDT / SOT-masked / 混合模式，机制不变 | 按老经验用 |
| none | 不迁移 | dst 与 src 光照本来接近时 |

### 其他合成参数

| 参数 | 说明 |
|---|---|
| erode/blur_mask_modifier 双向滑条 | 侵蚀/模糊 ±100，4.0.8.3 修了双向滑条与绝对值处理 |
| output_face_scale | 脸缩放 -50~+50 |
| super_resolution_power | 超分 0–100 |
| sharpen off/box/gaussian | 锐化模式+强度 |
| motion_blur / image_denoise / bicubic_degrade | 运动模糊/去噪/双三次降质，用于把预测脸"做旧"以匹配 dst 画质 |
| face_margin | 人脸边距 0.0–2.0 |
| detect_mode | 检测模式：skip_dfl（跳过已有 aligned，默认）等 |
| Debug 切换 | 显示遮罩/边框等调试图 |
| 导出 | FFmpeg NVENC 硬件加速（4.0.7 起批量导出支持 GPU 解码加速） |

## 四、DFM/ONNX 推理

- `--dfm-onnx`：合成时用 ONNX DFM 模型直接推理（免 PyTorch 模型加载，快）
- `--xseg-onnx` + `--xseg-onnx-res`（128/256）：ONNX XSeg/XSegLite 遮罩。**已就位**：workspace\model\XSeg\xseg.onnx、XSegLite\xseglite.onnx
- exportdfm：把训练好的模型导出成 DeepFaceLive 用的 DFM
- tools/export_onnx_to_trt.py：ONNX → TensorRT engine（XSegLite TRT FP16 1.46ms/684fps）

## 五、新模型类型对比

| 模型 | 与老 DFL 关系 | 适合场景 |
|---|---|---|
| SAEHD（PyTorch 版） | 参数兼容老 SAEHD；pretrain 停用换成新预训练机制 | 通用标准选择 |
| DeepFakeLarge / LIAELarge | 大模型，新增逐模块冻结组 | 高分辨率/大脸集 |
| **DFLite 架构**（4.0.8，archi 加 l 后缀） | 参数 -25.3%、推理 1.95× | 显存紧张或推理速度优先 |
| **DFSingle** | DF 架构去掉 dst_decoder：参数 -35%、训练 +30%，现有 DF 权重直接迁移（models/Model_DFSingle/migrate_from_saehd.py --src-dir ... --name ... --dst-dir ...） | 已有 DF 模型想提速 |
| AMP | morph_factor inter mixing + 双尺度 dssim + TV 正则 + 眼嘴优先，可选 GAN | 追求形变自然度 |
| FaceRestoreLite | 人脸修复轻量模型 | 老素材修复 |
| XSegLite | 原创，SimpleGate+FP32 锁定，ONNX 2.5ms vs 原版 10.4ms | XSeg 全兼容替代，速度快 4× |

## 六、参数搭配速查（常见目标 → 推荐组合）

| 目标 | 推荐组合 |
|---|---|
| 画质差的 dst（噪点/压缩） | random_noise=y + random_occlusion=y |
| 夜戏/舞台强光 | random_color_power=0.3 + random_color_alg=direct |
| 合成边缘硬边 | edge_enhance_power=1–5 |
| 显存不够（OOM） | gradient_checkpointing=y 或 optimizer=lion 或 DFLite 架构 |
| 一直挂着训 | lr_plateau_factor=0.5（不要用 lr_cos） |
| 皮肤纹理塑料感 | vgg_perceptual_power=10–25（默认 0） |
| XSeg 遮罩太慢 | 换 XSegLite（onnx 或训练版） |
| 已有 DF 模型提速 | 迁移到 DFSingle |
| 复杂非线性色差 | 合成时 color_transfer=lut；一般用 rct，羽化遮罩用 mt |
