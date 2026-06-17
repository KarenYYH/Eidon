<#
.SYNOPSIS
  Eidon Windows 一键引导（方案 A 第一段）——把「装 WSL2 + GPU 透传」这层自动化。
  跑完后自动接力到 WSL 内的 install-wsl-full.sh，全程尽量只让你双击 + 回车。

.DESCRIPTION
  这脚本只负责 Windows 侧那层（WSL 内部的 Docker/HeyGem/CosyVoice 由 install-wsl-full.sh 接管）：
    1. 检测管理员权限、Windows 版本、NVIDIA 驱动
    2. 安装 WSL2 + Ubuntu-22.04（首次需重启）
    3. 重启后自动续跑：把项目拷进 WSL，调 install-wsl-full.sh

  跨重启靠一个标记文件 + 一次性「登录自启」实现：第一段装完 WSL 要求重启，
  重启登录后自动跑第二段，不用你记着回来再点。

.NOTES
  用法：右键「以管理员身份运行 PowerShell」，然后：
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\install-windows.ps1
  或直接右键脚本「使用 PowerShell 运行」（会自我提权）。
#>

[CmdletBinding()]
param(
  [string]$Distro   = "Ubuntu-22.04",
  [string]$RepoUrl  = "https://github.com/KarenYYH/Eidon.git",
  [switch]$Resume,                       # 内部用：重启后自启时带上
  [switch]$SkipCosyvoice                 # 透传给 WSL 脚本：不装声音克隆
)

$ErrorActionPreference = "Stop"
$Tag      = "EidonInstall"
$StateDir = Join-Path $env:LOCALAPPDATA "Eidon"
$StateFile= Join-Path $StateDir "install-state.json"
$RunOnce  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"

function Info($m){ Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "  ✓ $m" -ForegroundColor Green }
function Warn($m){ Write-Host "  !! $m" -ForegroundColor Yellow }
function Die($m){  Write-Host "  ✗ $m" -ForegroundColor Red; Read-Host "按回车退出"; exit 1 }

# ── 自我提权 ─────────────────────────────────────────────────────────────────
$admin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
  Info "需要管理员权限，正在提权重启本脚本…"
  $argline = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  if ($Resume){ $argline += " -Resume" }
  if ($SkipCosyvoice){ $argline += " -SkipCosyvoice" }
  Start-Process powershell -Verb RunAs -ArgumentList $argline
  exit 0
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# ── 跨重启续跑：注册一次性自启 ───────────────────────────────────────────────
function Register-Resume {
  $cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Resume"
  if ($SkipCosyvoice){ $cmd += " -SkipCosyvoice" }
  Set-ItemProperty -Path $RunOnce -Name $Tag -Value $cmd
  '{"phase":"await-reboot"}' | Set-Content $StateFile
}
function Clear-Resume {
  Remove-ItemProperty -Path $RunOnce -Name $Tag -ErrorAction SilentlyContinue
}

# ── 阶段 0：Windows 侧检查 ───────────────────────────────────────────────────
if (-not $Resume) {
  Info "0/3 检查 Windows 环境"
  $build = [int](Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber
  if ($build -lt 19041) { Die "Windows 版本过旧（build $build）。WSL2 需要 Win10 2004(19041)+ 或 Win11。" }
  Ok "Windows build $build（支持 WSL2）"

  # NVIDIA 驱动检测（装驱动这步无法可靠自动化，只检测 + 引导）
  $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }
  if ($gpu) {
    Ok "检测到 NVIDIA 显卡：$($gpu.Name)  驱动 $($gpu.DriverVersion)"
  } else {
    Warn "没检测到 NVIDIA 显卡。数字人/声音克隆需要 N 卡 GPU。"
    Warn "若你确有 N 卡，请先到 nvidia.com 装最新驱动再继续；只试核心功能可往下走。"
    if ((Read-Host "继续？(y/N)") -ne "y"){ exit 0 }
  }
}

# ── 阶段 1：安装 WSL2 + Ubuntu ───────────────────────────────────────────────
function Test-WslDistro {
  # wsl -l -q 输出含 UTF-16 噪声，统一过滤
  $list = (wsl.exe -l -q 2>$null) -replace "`0","" | ForEach-Object { $_.Trim() }
  return ($list -contains $Distro)
}

if (-not $Resume) {
  Info "1/3 安装 WSL2 + $Distro"
  if (Test-WslDistro) {
    Ok "$Distro 已安装，跳过"
  } else {
    Info "执行 wsl --install -d $Distro（装完需要重启）…"
    wsl.exe --install -d $Distro
    wsl.exe --set-default-version 2 2>$null
    Register-Resume
    Warn "WSL 已安装。现在【必须重启 Windows】。"
    Warn "重启后会自动弹出窗口续跑余下步骤（首次进 Ubuntu 可能让你设用户名/密码，设完别关窗）。"
    if ((Read-Host "立即重启？(y/N)") -eq "y"){ Restart-Computer -Force }
    else { Warn "稍后手动重启即可，本脚本会在登录后自动继续。" }
    exit 0
  }
}

# ── 续跑入口（重启后自启会带 -Resume）────────────────────────────────────────
if ($Resume) {
  Clear-Resume
  Info "检测到重启后续跑…"
}

# 走到这里说明 WSL+Distro 已就绪（首次安装分支已 exit）
if (-not (Test-WslDistro)) {
  Die "$Distro 仍未就绪。请打开一次「Ubuntu」完成首次初始化（设用户名/密码）后重跑本脚本。"
}

# ── 阶段 2：把项目放进 WSL + 验证 GPU 透传 ──────────────────────────────────
Info "2/3 准备 WSL 内的项目与 GPU"

# GPU 透传验证（在 WSL 里）
$nv = wsl.exe -d $Distro -- bash -lc "command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | head -1" 2>$null
if ($nv) { Ok "WSL 内 GPU 透传正常：$nv" }
else {
  Warn "WSL 内 nvidia-smi 无输出 —— GPU 未透传。"
  Warn "请确认 Windows 已装最新 NVIDIA 驱动（不要在 WSL 内装驱动），然后 wsl --shutdown 重进。"
  Warn "只试核心功能（免费 TTS、无数字人）可继续。"
}

# 把项目弄进 WSL 的 ~ 下（Linux 文件系统，避免 /mnt 慢）
$wslUser = (wsl.exe -d $Distro -- bash -lc 'echo $USER' 2>$null | ForEach-Object { $_.Trim() } | Select-Object -First 1)
$wslProj = "/home/$wslUser/Eidon"
$exists  = wsl.exe -d $Distro -- bash -lc "test -f $wslProj/deploy/install-wsl-full.sh && echo yes" 2>$null
if ($exists -match "yes") {
  Ok "项目已在 WSL：$wslProj"
} else {
  # 优先 git clone；脚本所在的 Windows 目录若是完整仓库则改用拷贝
  $here = Split-Path -Parent (Split-Path -Parent $PSCommandPath)   # deploy 的上级
  if (Test-Path (Join-Path $here "backend\requirements.txt")) {
    Info "从本地拷贝项目进 WSL（$here → $wslProj）…"
    $wslSrc = wsl.exe -d $Distro -- wslpath -a "$here" 2>$null | ForEach-Object { $_.Trim() } | Select-Object -First 1
    wsl.exe -d $Distro -- bash -lc "cp -r '$wslSrc' '$wslProj' && echo copied" 2>$null | Out-Null
  } else {
    Info "git clone 项目进 WSL（$RepoUrl）…"
    wsl.exe -d $Distro -- bash -lc "command -v git >/dev/null || (sudo apt-get update -y && sudo apt-get install -y git); git clone $RepoUrl $wslProj"
  }
  $exists = wsl.exe -d $Distro -- bash -lc "test -f $wslProj/deploy/install-wsl-full.sh && echo yes" 2>$null
  if ($exists -notmatch "yes") { Die "项目未能放入 WSL（$wslProj）。可手动 git clone 后再跑 deploy/install-wsl-full.sh。" }
  Ok "项目就位：$wslProj"
}

# ── 阶段 3：接力到 WSL 内一键脚本 ───────────────────────────────────────────
Info "3/3 进入 WSL 跑后半段（Docker / Eidon / HeyGem / CosyVoice）"
$flags = ""
if ($SkipCosyvoice) { $flags = " --skip-cosyvoice" }
Write-Host ""
Write-Host "──────── 以下为 WSL 内安装输出 ────────" -ForegroundColor Cyan
wsl.exe -d $Distro -- bash -lc "cd $wslProj/deploy && bash install-wsl-full.sh$flags"
$code = $LASTEXITCODE

Remove-Item $StateFile -ErrorAction SilentlyContinue
Write-Host ""
if ($code -eq 0) {
  Ok "全部完成。Windows 浏览器打开  http://localhost/  访问 Eidon。"
} else {
  Warn "WSL 脚本返回码 $code。多为 systemd 首次开启需 wsl --shutdown 后重跑，或某阶段网络失败。"
  Warn "可在 WSL 里单独重试某阶段：cd $wslProj/deploy && bash install-wsl-full.sh --only <docker|eidon|heygem|cosyvoice>"
}
Read-Host "按回车退出"
