# 工具速查索引（素材侧全景）

> 一页式备忘：该用哪个工具、命令、坑。配套脚本在作者 fork（github.com/liyoulu/DeepFaceLab-PyTorch，ui-dark 分支）`tools\`，复制到 `<DFL_ROOT>\tools\` 使用；命令均在 `<DFL_ROOT>` 下执行。
> 更新：2026-10-17

## 0. 先选对流程

| 场景 | 用哪条 |
|---|---|
| IG 账号图源收集（持续增量） | ig_harvest → blur → faceid → 人审（SOP-6） |
| 人物夹初始化（图片树批量首切） | person_extract 首切 → blur → faceid → 人审 → 入库 → 归位（SOP-6） |
| 视频源批量收集（单/多视频同一入口） | video_pipeline 一条龙（SOP-7） |

约定：切脸产物 `px<短边4位>__` 前缀命名（按名排序=按分辨率分组）；人审=faceid_browser（每组封面即预览）。

## A. 图片源收集 / 首切

| 工具 | 用途 | 命令 | 关键点/坑 |
|---|---|---|---|
| ig_harvest | IG 账号图源收集，账本增量防重切 | `python tools\ig_harvest.py --src <账号目录> --out <输出目录>` | 账本=源夹 `.dfl\harvest.csv`；重切单张=删行再跑；源文件不动 |
| person_extract | 人物夹首切（管线不含归位） | `python tools\person_extract.py --root <素材根> --out <输出目录> --recursive` | out 非空需 `--allow-nonempty`；扁平名兼容母图反查归位 |
| resolution_gate | blur 前分辨率门，<min 移 `filtered_by_res\` | `python tools\resolution_gate.py --input <dir> --min 256 --move` | 动态尺寸产物无最小脸门槛的补位 |

## B. 视频源

| 工具 | 用途 | 命令 | 关键点/坑 |
|---|---|---|---|
| video_pipeline | 切帧→全脸自适应切→查重→faceid→人工筛 UI 一条龙 | `python tools\video_pipeline.py --video-dir <视频夹> --out <输出目录> --dedup` | fps=1 PNG+HDR tonemap（无标签源自动回退）；多视频流水重叠；帧在=断点续跑；`--del-frames` 切完删帧；查重放聚类前 |

## C. 清洗分拣（blur → 查重 → faceid → 人审）

| 工具 | 用途 | 命令 | 关键点/坑 |
|---|---|---|---|
| blur 分档 | 清晰度 4 档，保留 medium+high | `python FacesetProcessor\Filter.py -i <dir> --mode blur --train-res <训练分辨率>` | 相对分位阈值**跨轮不可比**，同批素材一轮跑完 |
| phash 查重 | 重复脸移 `repeated\` | `python FacesetProcessor\Filter.py -i <dir> --mode repeated --threshold 0.98` | 可重复跑；已算过 phash 的走 metadata 缓存 |
| faceid 聚类 | DBSCAN 分簇 + noise | `python FacesetProcessor\Filter.py -i <dir> --mode faceid --eps 0.35` | eps：0.35 人审甜点 / 0.375 折中 / 0.45 无人值守；合并全集一次跑到位 |
| faceid_browser | 相册风人工筛 UI | `python tools\faceid_browser.py --root <dir>` | 固定 8104，启动自动接管单实例；单击选中/Shift 范围多选；删除=移 `.trash\<组>\` 可恢复；⇄合并到 `merged\`；**开给用户前 GET /api/groups 核对是当前目录的分组** |

## D. 归位入库

母图归位 = 有幸存入库脸图命中的源图移 `cutted\`，其余移 `filtered\`（按相对子夹结构复刻）。**入库之后才做、且只做一次**；`未匹配脸图` 应为 0（非 0 先查命名/递归口径）。并库到长期素材库永远最后一步、等用户点头。
