#!/usr/bin/env bash
# ── Eidon 离线包打包脚本（在「准备机」上跑，需联网）──────────────────────────
# 把目标机安装要用的大文件一次性下好，打成可拷贝的 eidon-offline/ 目录。
# 配合 deploy/README-Offline.md 使用：本脚本生成离线包，拷到目标机后按该文档安装。
#
# 准备机要求：与目标机【同架构 + 同 Python 版本】（都用 WSL2 Ubuntu 22.04 最稳），
# 否则 Python wheels 在目标机可能因找不到匹配版本而装不上。
#
# 用法（在准备机，Eidon 仓库的 deploy 目录里）：
#   bash prepare-offline.sh                  # 打包全部五项
#   bash prepare-offline.sh --cn             # 用国内镜像下载（推荐）
#   bash prepare-offline.sh --out ~/pkg      # 指定输出目录（默认 ./eidon-offline）
#   bash prepare-offline.sh --only models    # 只打某项：heygem|models|wheels|miniconda
#   bash prepare-offline.sh --whisper medium # Whisper 模型大小（默认跟 .env，没有则 small）
#
# 每项可独立重跑；已存在的产物默认跳过（--force 重做）。
set -uo pipefail

c_reset=$'\e[0m'; c_red=$'\e[31m'; c_grn=$'\e[32m'; c_ylw=$'\e[33m'; c_blu=$'\e[36m'
log()  { printf '%s==>%s %s\n' "$c_blu" "$c_reset" "$*"; }
ok()   { printf '%s  ✓%s %s\n' "$c_grn" "$c_reset" "$*"; }
warn() { printf '%s  !!%s %s\n' "$c_ylw" "$c_reset" "$*"; }
die()  { printf '%s  ✗ %s%s\n' "$c_red" "$*" "$c_reset" >&2; exit 1; }
step() { printf '\n%s════ %s ════%s\n' "$c_blu" "$*" "$c_reset"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"

# ── 参数 ─────────────────────────────────────────────────────────────────────
CN=0; ONLY=""; FORCE=0; OUT="$(pwd)/eidon-offline"; WHISPER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --cn) CN=1 ;;
    --force) FORCE=1 ;;
    --out) OUT="${2:?--out 需要路径}"; shift ;;
    --only) ONLY="${2:?--only 需要名字}"; shift ;;
    --whisper) WHISPER="${2:?--whisper 需要模型名}"; shift ;;
    -h|--help) sed -n '2,/^set /{/^set /d;s/^#\{0,1\} \{0,1\}//;p;}' "$0"; exit 0 ;;
    *) die "未知参数: $1（-h 看帮助）" ;;
  esac
  shift
done
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }

# Whisper 模型大小：命令行 > .env 的 WHISPER_MODEL > 默认 small
if [ -z "$WHISPER" ]; then
  WHISPER="$(grep -E '^WHISPER_MODEL=' "$BACKEND/.env" 2>/dev/null | head -1 | cut -d= -f2 | tr -d ' ')"
  [ -n "$WHISPER" ] || WHISPER="small"
fi

# pip 国内源参数
PIP_I=""
[ "$CN" -eq 1 ] && PIP_I="-i https://pypi.tuna.tsinghua.edu.cn/simple"

mkdir -p "$OUT" "$OUT/models" "$OUT/models/whisper" "$OUT/wheels"
log "输出目录: $OUT"
log "Whisper 模型: $WHISPER   国内镜像: $([ "$CN" -eq 1 ] && echo 开 || echo 关)"

# ── 1. HeyGem 镜像（docker save）────────────────────────────────────────────
if want heygem; then
  step "1/4 HeyGem 镜像 → heygem-images.tar"
  tar="$OUT/heygem-images.tar"
  if [ -s "$tar" ] && [ "$FORCE" -eq 0 ]; then
    ok "已存在，跳过（--force 重做）：$tar"
  elif ! command -v docker >/dev/null 2>&1; then
    warn "准备机没装 docker，跳过 HeyGem 镜像。装好 docker 后：bash prepare-offline.sh --only heygem"
  else
    HEYGEM_DIR="${HEYGEM_DIR:-$HOME/Duix.Heygem}"
    [ -d "$HEYGEM_DIR/.git" ] || git clone https://github.com/duixcom/Duix.Heygem "$HEYGEM_DIR" || warn "HeyGem 克隆失败。"
    COMPOSE=""
    for f in "$HEYGEM_DIR/docker-compose.yml" "$HEYGEM_DIR/docker-compose.yaml" "$HEYGEM_DIR"/deploy/docker-compose*.yml; do
      [ -f "$f" ] && { COMPOSE="$f"; break; }
    done
    if [ -z "$COMPOSE" ]; then
      warn "没找到 HeyGem 的 compose 文件，跳过。"
    else
      log "拉取 compose 引用的镜像（约 30G，慢）…"
      ( cd "$(dirname "$COMPOSE")" && docker compose -f "$COMPOSE" pull ) || warn "compose pull 部分失败，继续打包已拉到的。"
      # 提取 compose 里 image: 字段的镜像名
      imgs=$(grep -E '^\s*image:\s*' "$COMPOSE" | sed -E 's/^\s*image:\s*//; s/["'\''"]//g' | sort -u)
      if [ -z "$imgs" ]; then
        warn "compose 里没显式 image:（可能是 build 构建的），无法 save。请手动 docker images 后自行 docker save。"
      else
        log "打包镜像：$(echo "$imgs" | tr '\n' ' ')"
        # shellcheck disable=SC2086
        docker save -o "$tar" $imgs && ok "已生成 $tar（$(du -h "$tar" | cut -f1)）" || warn "docker save 失败。"
        echo "$imgs" > "$OUT/heygem-images.list"
      fi
    fi
  fi
fi

# ── 2. 模型：CosyVoice2 + Whisper ───────────────────────────────────────────
if want models; then
  step "2/4 模型（CosyVoice2-0.5B + Whisper $WHISPER）"
  # 2a. CosyVoice2 模型（优先 ModelScope，国内快）
  cosy_out="$OUT/models/CosyVoice2-0.5B"
  if [ -d "$cosy_out" ] && [ "$FORCE" -eq 0 ] && [ -n "$(ls -A "$cosy_out" 2>/dev/null)" ]; then
    ok "CosyVoice2 模型已存在，跳过：$cosy_out"
  else
    if python3 -c 'import modelscope' 2>/dev/null || pip install -q $PIP_I modelscope 2>/dev/null; then
      log "ModelScope 下载 CosyVoice2-0.5B…"
      python3 -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='$cosy_out')" \
        && ok "CosyVoice2 模型 → $cosy_out" \
        || warn "ModelScope 下载失败。可手动下后放到 $cosy_out（见 README-Offline.md 第 2 节）。"
    else
      warn "装不上 modelscope，跳过 CosyVoice 模型。手动下放到 $cosy_out。"
    fi
  fi
  # 2b. Whisper 模型（.pt 放进 models/whisper/）
  wpt="$OUT/models/whisper/$WHISPER.pt"
  if [ -s "$wpt" ] && [ "$FORCE" -eq 0 ]; then
    ok "Whisper 模型已存在，跳过：$wpt"
  elif python3 -c 'import whisper' 2>/dev/null || pip install -q $PIP_I openai-whisper 2>/dev/null; then
    log "下载 Whisper 模型 $WHISPER…"
    python3 -c "import whisper,os,shutil; whisper.load_model('$WHISPER'); src=os.path.expanduser('~/.cache/whisper/$WHISPER.pt'); shutil.copy(src,'$wpt')" \
      && ok "Whisper 模型 → $wpt" \
      || warn "Whisper 模型下载失败。"
  else
    warn "装不上 openai-whisper，跳过 Whisper 模型。"
  fi
fi

# ── 3. Python 依赖 wheels ────────────────────────────────────────────────────
if want wheels; then
  step "3/4 Python 依赖 → wheels/（含 torch）"
  if [ -n "$(ls -A "$OUT/wheels" 2>/dev/null)" ] && [ "$FORCE" -eq 0 ]; then
    ok "wheels 已存在，跳过（--force 重做）"
  elif [ ! -f "$BACKEND/requirements.txt" ]; then
    warn "没找到 $BACKEND/requirements.txt，跳过。"
  else
    log "pip download 全部依赖（torch 等大包，慢）…"
    # shellcheck disable=SC2086
    pip download $PIP_I -r "$BACKEND/requirements.txt" -d "$OUT/wheels" \
      && ok "wheels → $OUT/wheels（$(ls "$OUT/wheels" | wc -l | tr -d ' ') 个文件，$(du -sh "$OUT/wheels" | cut -f1)）" \
      || warn "pip download 失败（注意准备机架构/Python 版本要与目标机一致）。"
  fi
fi

# ── 4. Miniconda 安装器 ──────────────────────────────────────────────────────
if want miniconda; then
  step "4/4 Miniconda 安装器"
  mc="$OUT/Miniconda3-latest-Linux-x86_64.sh"
  if [ -s "$mc" ] && [ "$FORCE" -eq 0 ]; then
    ok "已存在，跳过：$mc"
  else
    if [ "$CN" -eq 1 ]; then
      url="https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    else
      url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    fi
    curl -fsSL "$url" -o "$mc" && ok "Miniconda 安装器 → $mc" || warn "下载失败：$url"
  fi
fi

# ── 清单 + 总结 ──────────────────────────────────────────────────────────────
step "打包完成"
{
  echo "# Eidon 离线包清单  生成于 $(date '+%Y-%m-%d %H:%M:%S')"
  echo "# Whisper 模型: $WHISPER   国内镜像: $([ "$CN" -eq 1 ] && echo yes || echo no)"
  echo "# 准备机: $(uname -m) / python $(python3 -V 2>&1 | cut -d' ' -f2)"
  echo ""
  ( cd "$OUT" && du -ah --max-depth=2 . 2>/dev/null | sort -rh | head -30 )
} > "$OUT/MANIFEST.txt"

echo ""
echo "${c_grn}离线包就绪：$OUT${c_reset}"
echo "  总大小：$(du -sh "$OUT" 2>/dev/null | cut -f1)"
echo "  清单：$OUT/MANIFEST.txt"
echo ""
echo "下一步：把整个 $OUT 目录拷到目标机，按 deploy/README-Offline.md 安装。"
echo "  · HeyGem 镜像：docker load -i heygem-images.tar"
echo "  · CosyVoice 模型：server.py --model_dir <拷过去的 models/CosyVoice2-0.5B>"
echo "  · Whisper：cp models/whisper/$WHISPER.pt ~/.cache/whisper/"
echo "  · Python 依赖：pip install --no-index --find-links wheels -r backend/requirements.txt"
echo "  · Miniconda：bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3"
