# shenbian-skill — 深变（DeepFaceLab-PyTorch）AI Agent 实操手册

面向 [DeepFaceLab-PyTorch](https://github.com/CaijiPlayer258/DeepFaceLab-PyTorch)（深变 / DFL-Torch，作者 @菜级玩家）的 **skill 包**：把「素材 → 切脸 → 清洗 → 训练 → MergeStudio 合成 → 导出」全流程装进你的 AI agent（AutoClaw / Claude Code / 任何支持 SKILL.md 约定的 agent），让 agent 按实测 SOP 操作深变，而不是现学现猜。

## 一行安装

**推荐：Vercel skills CLI（多 agent 通吃，自动发现你装了哪些 agent）**：

```bash
npx skills add liyoulu/shenbian-skill
```

装完后对 agent 说「深变」或「DFL-PyTorch」即可触发。（Claude Code / Codex / OpenClaw / Copilot 等 79 种 agent 自动识别；加 `-g` 装到用户级，默认项目级。）

**AutoClaw（Windows PowerShell）**：

```powershell
irm https://raw.githubusercontent.com/liyoulu/shenbian-skill/main/install.ps1 | iex
```

（装到 `~\.agents\skills\shenbian`；Mac/Linux 或手动安装见下方。）

**手动安装（任何 agent）**：

```bash
git clone --depth 1 https://github.com/liyoulu/shenbian-skill.git "$HOME/.agents/skills/shenbian"
```

装完后对 agent 说「深变」或「DFL-PyTorch」即可触发；触发词与内容路由见 [SKILL.md](SKILL.md)。

## 里面有什么

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 主手册：全流程总览、常见任务 SOP、排障速查、环境基线 |
| `tool-index.md` | **素材侧工具速查**：IG/人物夹/视频收集、blur/faceid/查重、人工筛 UI、归位入库 |
| SKILL.md「SOP-6/7」 | **批量收集流程**：图片漏斗（ig_harvest/person_extract/blur/faceid/人审/归位）与视频流水线（单/多视频一条龙） |
| `references/quickstart.md` | **零基础一条龙**：六步命令链，每步带「照抄就能跑」的默认值 |
| `references/landmarker-selection.md` | 15 检测器 × 8 标记器实测选型（含云/框比自检法） |
| `references/data-processing.md` | 脸集清洗：faceid 拆身份、blur 剔糊、GUI↔CLI 对照 |
| `references/new-params-guide.md` | 深变独有训练参数深度说明 |
| SKILL.md「训练调参速查」 | **起训默认模板 + 信号→动作表 + 增强分阶段律 + ct_mode 决策线（rct→mt→lut）** |
| `references/mergestudio-params.md` | **MergeStudio 合成滑块全家桶**：mode/mask/erode/ctm/超分，含固定调参顺序 |
| `references/merge-workflow.md` | 端到端流程细节、与老 DFL 差异、HDR/AV1 实测 |
| `tools/doctor.py` | **环境自检**：根目录/modelhub/ffmpeg/CUDA/XSeg/磁盘/fork 增强，`--json` 机器可读，agent 激活先跑 |
| `tools/marker_probe/` | 检测器/标记点实测装置（`DFL_ROOT` 环境变量或自动探测，均支持 `--check` 自检） |
| `tests/` + CI | pytest 测试基线（无需装深变即可跑，fixtures 模拟仓库骨架）+ GitHub Actions |

## 前置要求

- 深变本体已安装（含 modelhub 模型包、ffmpeg）——安装方法见[上游 README](https://github.com/CaijiPlayer258/DeepFaceLab-PyTorch)
- NVIDIA GPU
- 脚本工具需设 `DFL_ROOT` 环境变量指向深变根目录（不设则自动探测 F:/C:/D: 常见位置）

## 反馈与更新

- 实测数据基于官方 v4.0.9（2026-09/10）；上游进入低维护模式，参数面变化时应重校
- 问题请开 issue；欢迎 PR 补充实测数据（注明 GPU 型号与素材规格）

## 许可

内容（文档）以 CC BY 4.0 发布；`tools/` 下脚本为 MIT。上游 DeepFaceLab-PyTorch 为 GPL-3.0，本项目仅引用其接口不改其代码。
