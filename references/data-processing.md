# 深变数据处理：脸图筛选 / 分组 / 清洗

> GUI 入口：主界面侧栏第 3 个图标「数据处理」（散点图标）。
> CLI 引擎：`FacesetProcessor/Filter.py`、`Sorter.py`、`Analyzer.py`（与 GUI 同一引擎）。
> 典型场景：切脸完成后，拆分多人身份、剔除模糊脸、去重，得到干净的目标人物脸集。

## 人脸集路径约定

- 路径 = aligned 目录（含 DFLJPG 人脸 + metadata.h5）
- 深变默认：`<DFL_ROOT>\workspace\<视频名>\aligned`
- 本项目实例（<示例片>）：`<素材库>/DST\shenbian_<片名>`（Junction，实体在 D 盘脸集库）
- 提取时已写入 metadata.h5（landmarks/rect 等），Filter/Sorter 直接复用，不重复计算几何量

## 四种过滤模式（Filter.py）

| 模式 | 功能 | 关键参数 |
|---|---|---|
| blur | 模糊剔除：高频/低频能量比清晰度指标，阈值自动标定（数据集分位 10/30/60），可 --absolute 用 σ=1/2 高斯模糊绝对基准 | --train-res 与训练分辨率一致（如 416） |
| faceid | **按身份聚类**：ArcFace embedding + DBSCAN，把多身份脸集拆成 faceid_group_XXX 子文件夹 | --eps 0.3（聚类半径）、--min-samples 2、--model w600k_mbf（快）/w600k_r50（准） |
| position | 按人脸位置聚类分组 | --threshold |
| repeated | 重复脸去重 | --threshold 0.98 |

## 指定人物保留流程（多人素材标准玩法）

```powershell
Set-Location <DFL_ROOT>

# 1) 身份聚类（在 aligned 目录内生成 faceid_group_XXX 子文件夹）
.\python\python.exe FacesetProcessor\Filter.py `
  --input "<素材库>/DST\shenbian_<片名>" `
  --mode faceid --eps 0.3 --min-samples 2 --model w600k_mbf

# 2) 人工目检各 group 的代表帧，确定目标人物所在文件夹
#    （运行结束会输出每组张数；打开子文件夹肉眼确认）

# 3) 其余身份文件夹移走（回收站/移出 aligned），只留目标组

# 4) 合并回 aligned 根目录（DFL 扁平结构，供训练/合成读取）
.\python\python.exe FacesetProcessor\Filter.py `
  --input "<素材库>/DST\shenbian_<片名>" --merge-only
```

- --merge-only：只把子文件夹合回根目录，不做聚类（用于挑选后归位）
- --merge-back：聚类后全部合回（用于"只是看看分组、不删任何组"的场合）
- noise 点（DBSCAN 标 -1 的孤立脸）的处理以运行输出说明为准

## 模糊清洗流程（建议在身份筛选之后、对保留集跑）

```powershell
.\python\python.exe FacesetProcessor\Filter.py `
  --input "<素材库>/DST\shenbian_<片名>" `
  --mode blur --train-res 416
```

- 阈值自动标定：blurry / low / medium 三档 + 中位等效模糊 σ 报告
- 误杀捞回：blurry 子文件夹目检，把好脸移回根目录即可
- 二轮筛选：对 medium 档再跑一次更严阈值

## 其他工具

- **Sorter**：phash/hist/blur/face_pose/resolution/color（姿态排序可选 pitch/yaw/roll）——排序输出到子目录，便于按量取脸
- **Analyzer**：features = phash,histogram,hue,pose,embedding,landmark 写元数据库（GUI「分析器」区块），faceid 复用 embedding
- **Pack**：`main.py util --input-dir <aligned> --pack-faceset` 打包 faceset.pak（单文件归档；注意 pak≈jpg 原体积，无压缩收益）

## GUI 等价操作

主界面「数据处理」页四区块与上述 CLI 一一对应：分析器 / 过滤器（四模式+合并按钮）/ 排序器 / PAK 解包与可视化。交互调参用 GUI，批量用 CLI。

## 脸集实体存放规则（2026-09-30 用户指定，两段式生命周期）

1. **切脸产物（活跃工作流）→ 默认放 C 盘 SSD**：<老DFL-MVE安装根>\workspace_ssd\dst\<片名>\，workspace 里 Junction 指过去。提取/筛选/质检/训练全在 SSD 上跑（HDD 上大规模文件操作太慢：rename 元数据地板 16-300 文件/秒 + 读取慢）
2. **沉淀（筛选定稿）→ 移到 D 盘脸集库**：<素材库>/DST\<片名>\（长期归档）。由用户手动移动，或让 agent 执行（跨盘移动 = 真实复制，SSD 目标速度快）

- Junction 建法：New-Item -ItemType Junction -Path "<workspace>\<视频名>\aligned" -Target "<SSD实体目录>"
- <示例片> 本片：产物已落在 D 盘（历史习惯），保持现状不迁移

## 实例记录（<示例片>，2026-09-30）

- 输入：135,714 张（含第二人 + 零星误检），预计 2-4 个身份组
- 聚类参数：eps 0.3 / min-samples 2 / w600k_mbf
- 后续：挑定楓ふうあ组 → 其余移出 → merge-only → blur --train-res 416 → 目检 → 训练/合成

## 身份筛选的标准做法（2026-09-30 实测补充，<示例片> 实例）

深变内置的可视化**不提供"按身份分组的并排拼图"**（内置只有：GUI 数据处理页「数据可视化」→ `samplelib/serve_angle_view.py`
的角度散点图 + 人脸缩略图；以及 `Sorter.py --rename` 把脸按清晰度/姿态/分辨率重命名后"开文件夹当缩略图长条看"）。
所以按身份挑人要用下面的流程：

```powershell
Set-Location <DFL_ROOT>
# ① 聚类（21k 张约 6-7 分钟：embedding 提取 + DBSCAN）
.\python\python.exe FacesetProcessor\Filter.py -i "<aligned目录>" --mode faceid --eps 0.3 --min-samples 2 --model w600k_mbf
# ② 每个组做一张拼图（每组抽 12 张、带组名/张数/占比）→ 人工目检
.\python\python.exe tools\marker_probe\make_contact_sheet.py "<aligned目录>"
#    拼图输出到 <aligned目录>\_idcheck\faceid_group_XXX.png，**看完建议挪到 aligned 外面**
# ③ 其余组先移到隔离目录（不要直接销毁，便于回滚）
#    建议 <工程目录>\_removed_ids\ ，确认无误后再送回收站
# ④ 只把保留的组合回根目录（DFL 要扁平结构）
.\python\python.exe FacesetProcessor\Filter.py -i "<aligned目录>" --merge-only
```

### 目检工具 `make_contact_sheet.py`（通用，两种模式自动切换）

```powershell
Set-Location <DFL_ROOT>
# 分组模式：目录里有 faceid_group_* / faceid_noise 子目录 → 每组一张拼图（组名+张数+占比）
.\python\python.exe tools\marker_probe\make_contact_sheet.py "<aligned目录>"
# 平铺模式：目录里直接是脸图 → 一张总览图（看切脸质量、取景一致性）
.\python\python.exe tools\marker_probe\make_contact_sheet.py "<aligned目录>" --out "D:\check_quality" --cols 6 --rows 4 --cell 160
```

参数：`--out` 输出目录（默认 `<目录>\_idcheck`）／`--cols --rows --cell` 网格与格子像素／
`--seed` 采样可复现／`--pattern "*.jpg,*.png"`／`--mode auto|group|flat`／`--title` 平铺标题。
读图走 `np.fromfile`+`imdecode`，中文/表情符路径安全；采样等间隔，同 seed 结果一致。

**铁律：输出目录不要放在 aligned 里面** —— `--merge-only` 会把 `_idcheck` 当成一组把 PNG 卷回脸集
（2026-09-30 实测踩过，脚本已把默认输出放 `<目录>\_idcheck`，但用完仍建议挪到 face 目录之外）。

**实测口径（<示例片>，20,476 张，eps 0.3）**：出 **95 组 + 噪声 140**，
最大组 17,545（85.7%，基本就是女主），其后 818 / 267 / 243 / 170 / 159 / 116 / 103…
→ **eps 0.3 偏保守、组数会很碎**（同一人因角度/遮挡被拆成多组）。想"一眼挑准"可把 `--eps` 提到 0.45–0.5 重跑（通常压到 3–8 组）。

**两个坑**：
- 拼图目录 `_idcheck` 千万别留在 aligned 里——`--merge-only` 会把它当成一组把 PNG 卷回脸集；
- 隔离用"先移出 aligned、确认后再送回收站"，别在聚类结果还没确认时直接删（删错了要重跑 6-7 分钟）。

