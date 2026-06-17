#!/usr/bin/env bash
# ── Eidon WSL2 全套一键安装（在 WSL2/Ubuntu 内运行）─────────────────────────
# 把 Eidon 主程序 + HeyGem(数字人) + CosyVoice2(声音克隆) 一条命令装完。
# 面向「要全套数字人」的用户：你只管跑这一条，脚本负责后半段全部脏活。
#
# 前置（Windows 侧，见 README-Windows.md 第 0 步 / install-windows.ps1）：
#   已装好 NVIDIA 驱动、已 `wsl --install -d Ubuntu-22.04`、`nvidia-smi` 在 WSL 里有输出。
#
# 用法（在 WSL2 里）：
#   cd ~/Eidon/deploy
#   bash install-wsl-full.sh                 # 全装
#   bash install-wsl-full.sh --skip-cosyvoice # 不要声音克隆（只 edge 免费 TTS）
#   bash install-wsl-full.sh --only heygem    # 只跑某一阶段（debug/重试用）
#
# 幂等：可反复运行；每阶段会先检测是否已就绪再决定跳过。
set -uo pipefail

# ── 日志 ─────────────────────────────────────────────────────────────────────
c_reset=$'\e[0m'; c_red=$'\e[31m'; c_grn=$'\e[32m'; c_ylw=$'\e[33m'; c_blu=$'\e[36m'
log()   { printf '%s==>%s %s\n' "$c_blu" "$c_reset" "$*"; }
ok()    { printf '%s  ✓%s %s\n' "$c_grn" "$c_reset" "$*"; }
warn()  { printf '%s  !!%s %s\n' "$c_ylw" "$c_reset" "$*"; }
die()   { printf '%s  ✗ %s%s\n' "$c_red" "$*" "$c_reset" >&2; exit 1; }
step()  { printf '\n%s════ %s ════%s\n' "$c_blu" "$*" "$c_reset"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
RUN_USER="${SUDO_USER:-$(whoami)}"
HOME_DIR="$(getent passwd "$RUN_USER" 2>/dev/null | cut -d: -f6)"
[ -n "$HOME_DIR" ] || HOME_DIR="$(eval echo "~$RUN_USER")"
[ -d "$HOME_DIR" ] || HOME_DIR="$HOME"
HEYGEM_DIR="$HOME_DIR/Duix.Heygem"
COSY_DIR="$HOME_DIR/CosyVoice"

# ── 参数 ─────────────────────────────────────────────────────────────────────
SKIP_COSY=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-cosyvoice) SKIP_COSY=1 ;;
    --only) ONLY="${2:-}"; shift ;;
    -h|--help) sed -n '2,/^set /{/^set /d;s/^#\{0,1\} \{0,1\}//;p;}' "$0"; exit 0 ;;
    *) die "未知参数: $1（-h 看帮助）" ;;
  esac
  shift
done
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }

# 需要 sudo（脚本本身别用 root 跑，里面按需 sudo，保持文件属主正确）
if [ "$(id -u)" -eq 0 ]; then
  die "请用普通用户跑（不要 sudo bash）。脚本会在需要时自己调 sudo。"
fi
sudo -v || die "需要 sudo 权限。"

# ── 阶段 0：环境自检 ─────────────────────────────────────────────────────────
if want preflight; then
  step "0/6 环境自检"
  # 是否在 WSL 里
  if ! grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
    warn "看起来不在 WSL2 里。本脚本是为 WSL2 写的，纯 Linux 服务器请改用 setup.sh + README.md。"
  else
    ok "运行环境: WSL2"
  fi
  # GPU 透传
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    ok "GPU 已透传: ${gpu:-未知}"
  else
    warn "WSL 里 nvidia-smi 无输出。数字人/声音克隆需要 GPU。"
    warn "请确认 Windows 已装最新 NVIDIA 驱动、且未在 WSL 内重复装驱动；然后 PowerShell 跑 wsl --shutdown 重进。"
    warn "（仅试核心功能可继续；要数字人请先修好 GPU。）"
  fi
  # 磁盘空间（HeyGem 镜像 ~30G + 模型）
  avail=$(df -BG --output=avail "$HOME_DIR" 2>/dev/null | tail -1 | tr -dc '0-9')
  if [ -n "${avail:-}" ] && [ "$avail" -lt 80 ]; then
    warn "可用磁盘 ${avail}G，全套(HeyGem 镜像≈30G + 模型)建议 ≥80G，可能不够。"
  else
    ok "磁盘空间: ${avail:-?}G 可用"
  fi
  # 项目就位
  [ -f "$BACKEND/requirements.txt" ] || die "未找到 $BACKEND/requirements.txt —— 确认在 ~/Eidon/deploy 里跑。"
  case "$ROOT" in /mnt/*) warn "项目在 /mnt/（Windows 盘），WSL 读写极慢。强烈建议拷到 ~ 下再跑。";; esac
  ok "项目路径: $ROOT"
fi

# ── 阶段 1：WSL 启用 systemd ─────────────────────────────────────────────────
if want systemd; then
  step "1/6 启用 systemd（Eidon 后端用）"
  if [ "$(systemctl is-system-running 2>/dev/null || true)" = "" ] || ! systemctl list-units >/dev/null 2>&1; then
    log "写入 /etc/wsl.conf 开启 systemd…"
    sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
    warn "systemd 尚未生效。请到 Windows PowerShell 执行：  wsl --shutdown"
    warn "等几秒后重新进入 WSL，再跑一次本脚本（会自动从这里继续）。"
    exit 0
  fi
  ok "systemd 已就绪（$(systemctl is-system-running 2>/dev/null || echo running)）"
fi

# ── 阶段 2：Docker + NVIDIA Container Toolkit（HeyGem 用）─────────────────────
if want docker; then
  step "2/6 安装 Docker + NVIDIA Container Toolkit"
  if ! command -v docker >/dev/null 2>&1; then
    log "安装 Docker Engine…"
    curl -fsSL https://get.docker.com | sudo sh || die "Docker 安装失败，检查网络后重试：bash install-wsl-full.sh --only docker"
    sudo usermod -aG docker "$RUN_USER"
    warn "已把 $RUN_USER 加入 docker 组 —— 需要重新进 WSL 才免 sudo。本次运行仍会用 sudo 兜底。"
  else
    ok "Docker 已装：$(docker --version 2>/dev/null)"
  fi
  # docker 命令包装：当前 shell 可能还没拿到 docker 组权限
  DOCKER="docker"; docker ps >/dev/null 2>&1 || DOCKER="sudo docker"

  if ! $DOCKER info 2>/dev/null | grep -qi nvidia; then
    log "安装 NVIDIA Container Toolkit…"
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
      sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
      sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
    sudo apt-get update -y && sudo apt-get install -y nvidia-container-toolkit \
      || die "NVIDIA Container Toolkit 安装失败。重试：bash install-wsl-full.sh --only docker"
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker 2>/dev/null || sudo service docker restart
  fi
  # 验证容器能用 GPU
  if $DOCKER run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    ok "容器 GPU 直通验证通过（--gpus all 可用）"
  else
    warn "容器内跑 GPU 失败。HeyGem 将无法用显卡。先确认阶段 0 的 nvidia-smi 正常。"
  fi
fi

# ── 阶段 3：Eidon 主程序（复用 setup.sh）─────────────────────────────────────
if want eidon; then
  step "3/6 部署 Eidon 主程序"
  if [ -f /etc/systemd/system/eidon-backend.service ] && systemctl is-active --quiet eidon-backend 2>/dev/null; then
    ok "eidon-backend 已在运行，跳过 setup.sh（如需重装：bash setup.sh）"
  else
    log "运行 setup.sh（装 ffmpeg+字体+Node+Nginx、建 venv、构建前端、systemd+nginx）…"
    sudo bash "$ROOT/deploy/setup.sh" || die "setup.sh 失败，看上面报错。"
  fi
  # 健康检查
  for i in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:8000/api/system/health >/dev/null 2>&1; then
      ok "后端健康检查通过 (127.0.0.1:8000)"; break
    fi
    [ "$i" -eq 20 ] && warn "后端 20 次健康检查未通过，看日志：journalctl -u eidon-backend -e"
    sleep 2
  done
  grep -q '填你的key' "$BACKEND/.env" 2>/dev/null && \
    warn "backend/.env 的 LLM_API_KEY 还是占位符 —— 填入 DeepSeek key 后：sudo systemctl restart eidon-backend"
fi

# ── 阶段 4：HeyGem（数字人，端口 8383）──────────────────────────────────────
# 最大的坑在这：HeyGem 跑在容器里，必须能按 Eidon 传的【绝对路径】读到人脸/音频文件。
# 脚本自动给 compose 注入「宿主路径==容器路径」的卷映射，避免让用户手改 yml。
if want heygem; then
  step "4/6 部署 HeyGem（数字人口型）"
  DOCKER="docker"; docker ps >/dev/null 2>&1 || DOCKER="sudo docker"
  if [ ! -d "$HEYGEM_DIR/.git" ]; then
    log "克隆 Duix.Heygem…"
    git clone https://github.com/duixcom/Duix.Heygem "$HEYGEM_DIR" \
      || die "HeyGem 克隆失败，检查网络后重试：bash install-wsl-full.sh --only heygem"
  else
    ok "Duix.Heygem 已存在：$HEYGEM_DIR"
  fi
  # 找 compose 文件
  COMPOSE=""
  for f in "$HEYGEM_DIR/docker-compose.yml" "$HEYGEM_DIR/docker-compose.yaml" "$HEYGEM_DIR"/deploy/docker-compose*.yml; do
    [ -f "$f" ] && { COMPOSE="$f"; break; }
  done
  [ -n "$COMPOSE" ] || die "没找到 HeyGem 的 docker-compose 文件，可能官方目录结构变了。手动按其 README 起服务后用 --skip 跳过。"
  ok "compose 文件: $COMPOSE"

  # 自动注入卷映射：宿主 $BACKEND -> 容器内同路径。用 python 改 yml 最稳。
  MOUNT="$BACKEND:$BACKEND"
  if grep -qF "$MOUNT" "$COMPOSE"; then
    ok "卷映射已存在，跳过注入"
  else
    log "向 face2face 服务注入卷映射：$MOUNT"
    cp "$COMPOSE" "$COMPOSE.eidon.bak"
    python3 - "$COMPOSE" "$BACKEND" <<'PY' || { warn "自动注入失败，已还原。请手动在 compose 的 face2face 服务下加：  - $BACKEND:$BACKEND"; cp "$COMPOSE.eidon.bak" "$COMPOSE"; }
import sys, re
path, backend = sys.argv[1], sys.argv[2]
try:
    import yaml
except ImportError:
    import subprocess; subprocess.check_call([sys.executable,"-m","pip","install","-q","pyyaml"]); import yaml
with open(path) as f: doc = yaml.safe_load(f)
svcs = doc.get("services", {})
# 优先匹配 face2face / f2f；否则选第一个用 GPU 的服务
target = next((n for n in svcs if re.search(r"face2face|f2f", n, re.I)), None)
if not target:
    target = next((n for n,s in svcs.items() if "deploy" in (s or {}) and "gpu" in str(s).lower()), None)
if not target:
    target = next(iter(svcs), None)
if not target:
    print("NO_SERVICE"); sys.exit(1)
svc = svcs[target] or {}
vols = svc.get("volumes") or []
m = f"{backend}:{backend}"
if m not in vols:
    vols.append(m); svc["volumes"] = vols; svcs[target] = svc
    with open(path,"w") as f: yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
print("OK:"+target)
PY
    ok "已注入（备份在 $COMPOSE.eidon.bak）"
  fi

  log "拉起 HeyGem（首次拉镜像约 30G，耐心等）…"
  ( cd "$(dirname "$COMPOSE")" && $DOCKER compose -f "$COMPOSE" up -d ) \
    || die "docker compose up 失败。看 $DOCKER compose -f \"$COMPOSE\" logs"
  for i in $(seq 1 30); do
    curl -fsS http://127.0.0.1:8383/ >/dev/null 2>&1 && { ok "HeyGem 端口 8383 已响应"; break; }
    [ "$i" -eq 30 ] && warn "HeyGem 90s 内未响应，可能还在拉镜像/加载模型。稍后查：$DOCKER compose -f \"$COMPOSE\" ps"
    sleep 3
  done
fi

# ── 阶段 5：CosyVoice2（声音克隆，端口 50000）────────────────────────────────
# conda + pynini 是原生安装最大的坑。脚本尽量自动，失败给明确指引，不让小白卡死。
if want cosyvoice && [ "$SKIP_COSY" -eq 0 ]; then
  step "5/6 部署 CosyVoice2（声音克隆）"
  if curl -fsS http://127.0.0.1:50000/ >/dev/null 2>&1; then
    ok "CosyVoice 已在 50000 端口运行，跳过"
  else
    # conda 是否可用
    if ! command -v conda >/dev/null 2>&1; then
      log "未检测到 conda，安装 Miniconda（pynini 必须用 conda 装）…"
      mc="$HOME_DIR/miniconda3"
      curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/mc.sh \
        && bash /tmp/mc.sh -b -p "$mc" \
        || { warn "Miniconda 安装失败。可跳过声音克隆继续：先用 --skip-cosyvoice 装其余部分，TTS 用免费 edge。"; ONLY="__skip__"; }
      export PATH="$mc/bin:$PATH"
    fi
    if command -v conda >/dev/null 2>&1; then
      [ -d "$COSY_DIR/.git" ] || git clone --recursive https://github.com/FunAudioLLM/CosyVoice "$COSY_DIR" \
        || warn "CosyVoice 克隆失败，稍后重试：bash install-wsl-full.sh --only cosyvoice"
      if [ -d "$COSY_DIR" ]; then
        log "建 conda 环境 + 装 pynini + 依赖（较慢）…"
        eval "$(conda shell.bash hook)"
        conda env list | grep -q '^cosyvoice ' || conda create -n cosyvoice python=3.10 -y
        conda activate cosyvoice
        conda install -y -c conda-forge pynini==2.1.5 || warn "pynini 安装失败，CosyVoice 可能起不来。"
        ( cd "$COSY_DIR" && pip install -q -r requirements.txt ) || warn "CosyVoice 依赖装不全，看上面报错。"
        warn "CosyVoice 模型(CosyVoice2-0.5B)需手动下载后再起服务 —— 这步因模型体积大不自动跑。"
        warn "下模型并启动（在 cosyvoice 环境）："
        warn "  cd $COSY_DIR/runtime/python/fastapi"
        warn "  python server.py --port 50000 --model_dir <CosyVoice2-0.5B 模型路径>"
        warn "建议用 tmux 常驻，或写个 systemd unit。详见 README-Windows.md 第 4 步。"
      fi
    fi
  fi
elif [ "$SKIP_COSY" -eq 1 ]; then
  step "5/6 跳过 CosyVoice（--skip-cosyvoice）—— TTS 用免费 edge，无需声音克隆"
fi

# ── 阶段 6：端到端自检 ───────────────────────────────────────────────────────
if want verify; then
  step "6/6 四件套自检"
  tools_json=$(curl -fsS http://127.0.0.1:8000/api/system/tools 2>/dev/null || echo '{}')
  check() { echo "$tools_json" | grep -q "\"$1\":true" && ok "$2: 就绪" || warn "$2: 未就绪"; }
  check ffmpeg    "ffmpeg(字幕烧录)"
  check heygem    "HeyGem(数字人)"
  [ "$SKIP_COSY" -eq 1 ] || check cosyvoice "CosyVoice(声音克隆)"
  echo "$tools_json" | grep -q '"stock":true'   && ok "在线素材: 已配置"
  echo "$tools_json" | grep -q '"publish":true' && ok "自动发布: 已配置"

  cat <<EOF

${c_grn}════════════════════════════════════════════════════${c_reset}
  安装流程跑完。访问界面：
    Windows 浏览器打开  ${c_blu}http://localhost/${c_reset}   （WSL 端口自动转发）

  下一步：
   1) 没填 key 的话，编辑 backend/.env 填 LLM_API_KEY（DeepSeek），
      然后  sudo systemctl restart eidon-backend
   2) CosyVoice 模型按上面提示手动下载并起服务（要声音克隆才需要）
   3) 「素材」页上传人脸视频 + 参考音色，再跑「口播改写」

  运维：
    后端   sudo systemctl status eidon-backend   /  journalctl -u eidon-backend -f
    HeyGem cd $HEYGEM_DIR && docker compose ps
  排错对照表见  deploy/README-Windows.md 第 7 节
${c_grn}════════════════════════════════════════════════════${c_reset}
EOF
fi
