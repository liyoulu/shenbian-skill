# shenbian-skill 一行安装脚本（AutoClaw / 任何使用 .agents/skills 约定的 agent）
# 用法: irm https://raw.githubusercontent.com/liyoulu/shenbian-skill/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'

# 用户目录解析：pwsh 下 $HOME 可靠，Windows PowerShell 5.1 下回退 USERPROFILE
$UserHome = if ($HOME -and (Test-Path $HOME)) { $HOME } else { $env:USERPROFILE }
$skillDir = Join-Path $UserHome '.agents\skills\shenbian'
$repo = 'https://github.com/liyoulu/shenbian-skill.git'

function Clone-Repo([string]$dest) {
    git clone --depth 1 $repo $dest 2>$null
    return ($LASTEXITCODE -eq 0)
}

if (Test-Path (Join-Path $skillDir 'SKILL.md')) {
    Write-Host "[shenbian] 已存在 $skillDir，尝试更新（git pull）..." -ForegroundColor Yellow
    $updated = $false
    if (Test-Path (Join-Path $skillDir '.git')) {
        git -C $skillDir pull --ff-only 2>$null
        $updated = ($LASTEXITCODE -eq 0)
    }
    if (-not $updated) {
        # 非 git 目录或 pull 失败：先 clone 到临时目录，成功后才替换（旧目录只会被改名备份，永不删除）
        $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("shenbian-skill-" + [guid]::NewGuid().ToString('N').Substring(0,8))
        if (Clone-Repo $tmp) {
            $bak = "$skillDir.bak.$(Get-Date -Format yyyyMMdd_HHmmss)"
            Move-Item $skillDir $bak -Force
            Move-Item $tmp $skillDir -Force
            Write-Host "[shenbian] 更新完成，旧版备份在 $bak" -ForegroundColor Green
        } else {
            Write-Host "[shenbian] 下载失败，保留现有版本不动（$skillDir）" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[shenbian] 已更新到最新版" -ForegroundColor Green
    }
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $skillDir) | Out-Null
    if (-not (Clone-Repo $skillDir)) { throw "[shenbian] 安装失败：git clone 未成功，请检查网络/git，或手动 git clone $repo `"$skillDir`"" }
    Write-Host "[shenbian] 安装完成: $skillDir" -ForegroundColor Green
}

# 环境自检（非致命）
Write-Host "`n[shenbian] 环境自检:" -ForegroundColor Cyan
$hint = $false
if (-not $env:DFL_ROOT) {
    foreach ($c in @("F:\DFL-PyTorch", "C:\DFL-PyTorch", "D:\DFL-PyTorch", "$UserHome\DFL-PyTorch")) {
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
