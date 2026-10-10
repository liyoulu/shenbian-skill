# shenbian-skill 一行安装脚本（AutoClaw / 任何使用 .agents/skills 约定的 agent）
# 用法: irm https://raw.githubusercontent.com/liyoulu/shenbian-skill/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'

$skillDir = Join-Path $HOME '.agents\skills\shenbian'
if (Test-Path $skillDir) {
    Write-Host "[shenbian] 已存在 $skillDir，执行更新（git pull）..." -ForegroundColor Yellow
    git -C $skillDir pull --ff-only 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[shenbian] git pull 失败（可能有本地改动）。备份后重装..." -ForegroundColor Yellow
        Move-Item $skillDir "$skillDir.bak.$(Get-Date -Format yyyyMMdd_HHmmss)" -Force
        git clone --depth 1 https://github.com/liyoulu/shenbian-skill.git $skillDir
    }
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $skillDir) | Out-Null
    git clone --depth 1 https://github.com/liyoulu/shenbian-skill.git $skillDir
}

if ($LASTEXITCODE -ne 0) { throw "[shenbian] 安装失败：git clone 未成功，请检查网络或手动安装（见 README）" }

Write-Host "[shenbian] 安装完成: $skillDir" -ForegroundColor Green

# 环境自检（非致命）
Write-Host "`n[shenbian] 环境自检:" -ForegroundColor Cyan
$hint = $false
if (-not $env:DFL_ROOT) {
    foreach ($c in @("F:\DFL-PyTorch", "C:\DFL-PyTorch", "D:\DFL-PyTorch", "$HOME\DFL-PyTorch")) {
        if (Test-Path (Join-Path $c 'main.py')) {
            Write-Host "  [OK] 探测到深变: $c（建议 setx DFL_ROOT `"$c`" 永久生效）"
            $found = $c; break
        }
    }
    if (-not $found) { Write-Host "  [--] 未找到深变安装目录；装好后 setx DFL_ROOT <目录>"; $hint = $true }
} else {
    if (Test-Path (Join-Path $env:DFL_ROOT 'main.py')) { Write-Host "  [OK] DFL_ROOT = $env:DFL_ROOT" }
    else { Write-Host "  [!!] DFL_ROOT=$env:DFL_ROOT 下没有 main.py，请修正"; $hint = $true }
}

$skillMd = Join-Path $skillDir 'SKILL.md'
if (Test-Path $skillMd) {
    Write-Host "  [OK] SKILL.md 就位 ($((Get-Item $skillMd).Length) bytes)"
} else {
    Write-Host "  [!!] SKILL.md 缺失，安装可能不完整"; $hint = $true
}

Write-Host "`n[shenbian] 下一步: 对你的 agent 说「深变」试试，或直接读 references/quickstart.md 跑通全流程。" -ForegroundColor Cyan
