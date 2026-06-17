#!/usr/bin/env bash
# ── install-windows.ps1 的 WSL 侧助手 ───────────────────────────────────────
# 目的：把所有「带 &&、|、()、引号」的 shell 逻辑放在真正的 .sh 文件里由 bash 原生解析，
# 让 install-windows.ps1 永远只用最简单的方式调用——bash <本脚本> <子命令> <简单参数>，
# 彻底避开 PowerShell 解析嵌套 shell 命令时的引号/转义问题。
#
# 调用约定（PowerShell 侧）：
#   $p = (wsl -d $Distro -- wslpath -a "<本脚本的Windows路径>").Trim()
#   wsl -d $Distro -- bash $p <子命令> [参数...]
# 每个子命令把结果用「单行约定值」打到 stdout，PS 用字符串匹配判断。
set -uo pipefail

cmd="${1:-}"; shift 2>/dev/null || true

case "$cmd" in
  gpu)            # 打印 GPU 名（无则空）
    command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L 2>/dev/null | head -1
    ;;
  whoami)         # 打印 WSL 当前用户名
    id -un
    ;;
  has-project)    # $1=项目目录 → yes/no
    if [ -f "${1:-}/deploy/install-wsl-full.sh" ]; then echo yes; else echo no; fi
    ;;
  winpath)        # $1=Windows路径 → 对应的 WSL 路径
    wslpath -a "${1:-}"
    ;;
  fetch)          # $1=copy|clone  $2=源(本地路径或repo url)  $3=目标目录 → ok/fail/exists
    mode="${1:-}"; src="${2:-}"; dest="${3:-}"
    if [ -f "$dest/deploy/install-wsl-full.sh" ]; then echo exists; exit 0; fi
    if [ "$mode" = "copy" ]; then
      cp -r "$src" "$dest"
    else
      command -v git >/dev/null 2>&1 || { sudo apt-get update -y && sudo apt-get install -y git; }
      git clone "$src" "$dest"
    fi
    if [ -f "$dest/deploy/install-wsl-full.sh" ]; then echo ok; else echo fail; fi
    ;;
  run)            # $1=项目目录，其余参数原样转给 install-wsl-full.sh
    dir="${1:-}"; shift 2>/dev/null || true
    cd "$dir/deploy" && exec bash install-wsl-full.sh "$@"
    ;;
  *)
    echo "unknown bootstrap cmd: $cmd" >&2; exit 2
    ;;
esac
