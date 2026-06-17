#!/usr/bin/env bash
# ── Eidon 一键部署脚本（Ubuntu 22.04 / Linux GPU 服务器）──────────────────────
# 仅部署 Eidon 主程序本身（后端 + 前端）。CosyVoice2 / HeyGem 见 README.md 单独部署。
#
# 用法：
#   cd Eidon/deploy
#   sudo bash setup.sh
#
# 幂等：可重复运行。
set -euo pipefail

# 项目根目录（deploy 的上级）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$ROOT/.venv"
RUN_USER="${SUDO_USER:-$(whoami)}"

echo "==> 项目根目录: $ROOT"
echo "==> 运行用户:   $RUN_USER"

# 1) 系统依赖：ffmpeg(带libass)、中文字体、python、nginx、构建工具
echo "==> [1/6] 安装系统依赖…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  ffmpeg \
  fonts-noto-cjk \
  python3 python3-venv python3-pip \
  nginx \
  git curl ca-certificates

# yt-dlp 用 pip 装（apt 版本通常过旧）
# Node.js（构建前端）：装 LTS
if ! command -v node >/dev/null 2>&1; then
  echo "==> 安装 Node.js 20 LTS…"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# 验证 ffmpeg 带字幕滤镜
if ffmpeg -hide_banner -filters 2>/dev/null | grep -q " subtitles "; then
  echo "    ffmpeg subtitles 滤镜: OK"
else
  echo "    !! 警告: 此 ffmpeg 无 subtitles 滤镜，硬字幕将降级为无字幕。"
fi
# 验证中文字体
if fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
  echo "    中文字体 Noto Sans CJK: OK"
else
  echo "    !! 警告: 未检测到 Noto Sans CJK 字体，中文字幕可能显示方框。"
fi

echo "==> [1/6] 系统依赖完成"

# 2) Python 虚拟环境 + 后端依赖
echo "==> [2/6] 创建 venv 并安装后端依赖…"
# 国内镜像（由 install-wsl-full.sh 透传 EIDON_CN=1，或手动 EIDON_CN=1 sudo bash setup.sh）
PIP_I=""
if [ "${EIDON_CN:-0}" = "1" ]; then
  export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
  PIP_I="-i https://pypi.tuna.tsinghua.edu.cn/simple"
  echo "    pip 源 → 清华（EIDON_CN=1）"
fi
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install $PIP_I --upgrade pip
"$VENV/bin/pip" install $PIP_I -r "$BACKEND/requirements.txt"

# 可选：GPU 加速 Whisper —— 安装 CUDA 版 torch 会显著加快转写。
# 默认 requirements 装的是通用 torch；如需 GPU 版，取消下面注释并按显卡 CUDA 版本调整：
# "$VENV/bin/pip" install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121
echo "==> [2/6] 后端依赖完成"

# 3) .env 配置
echo "==> [3/6] 准备 .env…"
if [ ! -f "$BACKEND/.env" ]; then
  cp "$ROOT/deploy/.env.production.example" "$BACKEND/.env"
  echo "    已从模板创建 backend/.env —— 记得填入 LLM_API_KEY！"
else
  echo "    backend/.env 已存在，跳过（请自行核对配置）"
fi

# 4) 构建前端静态文件
echo "==> [4/6] 构建前端…"
cd "$FRONTEND"
if [ "${EIDON_CN:-0}" = "1" ]; then
  sudo -u "$RUN_USER" npm config set registry https://registry.npmmirror.com 2>/dev/null || true
  echo "    npm 源 → npmmirror（EIDON_CN=1）"
fi
sudo -u "$RUN_USER" npm install
sudo -u "$RUN_USER" npm run build
echo "    前端产物: $FRONTEND/dist"
echo "==> [4/6] 前端构建完成"

# 5) systemd 托管后端（单进程）
echo "==> [5/6] 安装 systemd 服务…"
SERVICE_SRC="$ROOT/deploy/eidon-backend.service"
SERVICE_DST="/etc/systemd/system/eidon-backend.service"
sed -e "s#<部署用户，如 ubuntu>#$RUN_USER#g" \
    -e "s#<项目路径>/Eidon#$ROOT#g" \
    "$SERVICE_SRC" > "$SERVICE_DST"
systemctl daemon-reload
systemctl enable --now eidon-backend
echo "    后端服务已启动 (127.0.0.1:8000)"

# 6) Nginx 托管前端 + 反代
echo "==> [6/6] 配置 Nginx…"
NGINX_DST="/etc/nginx/sites-available/eidon"
sed -e "s#<项目路径>/Eidon#$ROOT#g" "$ROOT/deploy/nginx-eidon.conf" > "$NGINX_DST"
ln -sf "$NGINX_DST" /etc/nginx/sites-enabled/eidon
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo "==> [6/6] Nginx 完成"

echo ""
echo "════════════════════════════════════════════════════"
echo "  Eidon 主程序部署完成。"
echo "  访问：http://<服务器IP>/"
echo ""
echo "  后端状态：sudo systemctl status eidon-backend"
echo "  后端日志：journalctl -u eidon-backend -f"
echo ""
echo "  下一步（见 deploy/README.md）："
echo "   1) 填好 backend/.env 的 LLM_API_KEY，重启：sudo systemctl restart eidon-backend"
echo "   2) 单独部署 CosyVoice2(:50000) 和 HeyGem(:8383)"
echo "   3) 在「素材」页上传人脸视频与参考音色"
echo "════════════════════════════════════════════════════"

