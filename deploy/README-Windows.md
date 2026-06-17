# Eidon — Windows + RTX 4090 部署指南（WSL2 全套）

本指南把 **Eidon 主程序 + CosyVoice2（声音克隆）+ HeyGem（数字人）** 全部跑在
**WSL2(Ubuntu)** 里，4090 通过 Windows 驱动透传进去。这是 Windows 上最省心的方案：

- 复用 Linux 那套部署脚本（`setup.sh` / systemd / nginx），无需 Windows 版
- 三个服务在同一个 Linux 文件系统里，**文件共享天然互通**（消掉最大的坑）
- 避开 CosyVoice 在原生 Windows 上 `pynini`/`WeTextProcessing` 的依赖地狱

> 显存预算：4090 有 24GB，HeyGem(~8GB) + CosyVoice(~4GB) + Whisper(~2GB) 同跑绰绰有余。

---

## 🚀 快速通道（推荐：两个脚本，少手敲命令）

不想照着下面 8 步手敲？用这两个脚本，大部分步骤自动化：

**第 1 步（Windows）—— 装 WSL2 + 自动接力**
先去 nvidia.com 装好显卡驱动（这步只能手动）。然后右键以**管理员身份**开 PowerShell：

```powershell
cd <项目所在目录>\Eidon\deploy
Set-ExecutionPolicy -Scope Process Bypass -Force
.\install-windows.ps1
```

它会：检测系统/显卡 → 装 WSL2+Ubuntu →（首次需重启，**重启后自动续跑**）→ 把项目放进 WSL → 自动调用第 2 步的脚本。一路 `y` + 回车即可。不要声音克隆就加 `-SkipCosyvoice`。

**第 2 步（WSL 内）—— 后半段全自动**
上面那个脚本会自动调它；你也可以单独在 WSL 里跑：

```bash
cd ~/Eidon/deploy
bash install-wsl-full.sh                 # 全装（Docker→Eidon→HeyGem→CosyVoice→自检）
bash install-wsl-full.sh --skip-cosyvoice  # 不要声音克隆（TTS 用免费 edge）
bash install-wsl-full.sh --only heygem     # 某阶段失败时单独重试
```

它会：开 systemd → 装 Docker+NVIDIA Toolkit → 跑 `setup.sh` 部署 Eidon → 克隆并起 HeyGem（**自动注入容器卷映射，免手改 yml**）→ 引导 CosyVoice → 四件套自检。每阶段幂等可重跑，失败会告诉你卡在哪、贴哪条命令重试。

> CosyVoice 的模型权重因为体积大（几个 G）不自动下载，脚本会在最后打印手动下载+启动命令（见第 4 步）。其余全自动。
> 这两个脚本无法替你做的只有两件：**装 NVIDIA 驱动** 和 **`wsl --install` 后的那次重启**——其它都包了。

下面的 8 步是完整手动流程 / 排错参考，按快速通道走顺了可不用逐条看。

---

## 0. Windows 侧准备（只做一次）

### 0.1 装最新 NVIDIA 驱动
到 nvidia.com 下载并安装 **GeForce RTX 4090 的最新 Game Ready / Studio 驱动**。
WSL2 的 CUDA 是靠这个 Windows 驱动透传的 —— **WSL 里不要再单独装 NVIDIA 驱动**。

### 0.2 装 WSL2 + Ubuntu 22.04
以**管理员身份**打开 PowerShell：

```powershell
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

装完重启，首次进入 Ubuntu 设个用户名密码。确认版本是 2：

```powershell
wsl -l -v        # VERSION 列应为 2
```

### 0.3 验证 GPU 已透传进 WSL2
进入 WSL2（开始菜单搜 "Ubuntu" 或 PowerShell 里敲 `wsl`）：

```bash
nvidia-smi       # 能看到 RTX 4090 就对了
```

看不到的话：更新 Windows 到最新、更新 NVIDIA 驱动、`wsl --update` 后再试。

---

## 1. 让 WSL2 支持 systemd（Eidon 后端用）

WSL2 默认不开 systemd。编辑配置：

```bash
sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
```

回到 **PowerShell** 重启 WSL 使其生效：

```powershell
wsl --shutdown
```

再次进入 WSL2，确认 systemd 起来了：

```bash
systemctl is-system-running      # running 或 degraded 都行
```

---

## 2. 在 WSL2 里装 Docker + NVIDIA Container Toolkit（HeyGem 用）

不要用 Docker Desktop —— 直接在 WSL2 里装原生 Docker 最干净：

```bash
# Docker Engine
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER         # 免 sudo（重新进 WSL 生效）

# NVIDIA Container Toolkit（让容器用上 4090）
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

退出并重进 WSL2，验证容器能用 GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
# 容器里能打印出 4090 即成功
```

---

## 3. 部署 Eidon 主程序

把项目拷进 WSL2（放 Linux 文件系统里，**不要**放 `/mnt/c/...`，否则极慢）：

```bash
cd ~
# 用 git 拉，或从 Windows 拷：cp -r /mnt/c/Users/你/Eidon ~/Eidon
cd ~/Eidon/deploy
sudo bash setup.sh
```

`setup.sh` 会装 ffmpeg(带 libass) + 中文字体 + Node + Nginx、建 venv、构建前端、装好 systemd + nginx。

然后填 LLM Key（翻译/改写用的 DeepSeek）：

```bash
nano ~/Eidon/backend/.env
# 至少填：LLM_API_KEY、LLM_BASE_URL=https://api.deepseek.com、LLM_MODEL=deepseek-v4-pro
sudo systemctl restart eidon-backend
```

验证：

```bash
curl http://127.0.0.1:8000/api/system/health      # {"status":"ok"...}
```

> GPU 加速 Whisper（可选但推荐）：默认 pip 装的是 CPU 版 torch。要让转写吃上 4090：
> ```bash
> source ~/Eidon/backend/.venv/bin/activate
> pip install torch --index-url https://download.pytorch.org/whl/cu124
> ```

---

## 4. 部署 CosyVoice2（声音克隆，端口 50000）

```bash
cd ~
git clone --recursive https://github.com/FunAudioLLM/CosyVoice
cd CosyVoice
# 建独立 conda/venv 环境，按官方 README 装依赖（pynini 用 conda 装最稳）
conda create -n cosyvoice python=3.10 -y && conda activate cosyvoice
conda install -y -c conda-forge pynini==2.1.5
pip install -r requirements.txt
# 下模型（CosyVoice2-0.5B）
# 然后起官方 fastapi runtime：
cd runtime/python/fastapi
python server.py --port 50000 --model_dir <CosyVoice2-0.5B模型路径> &
```

验证端口：`curl http://127.0.0.1:50000/`（能响应即可）。
Eidon 的 `.env` 默认 `COSYVOICE_HOST=http://localhost:50000`，同机无需改。

---

## 5. 部署 HeyGem（数字人口型，端口 8383）

```bash
cd ~
git clone https://github.com/duixcom/Duix.Heygem
cd Duix.Heygem
# 按官方 docker-compose 起服务（首次会拉 ~30GB 镜像，耐心等）
docker compose up -d
docker compose ps          # 容器都 Up
```

### ⚠️ 文件共享（全 WSL2 方案下最关键的一步）

Eidon 把人脸视频/音频的**路径**传给 HeyGem，HeyGem 容器内必须能按同一路径读到这些文件。做法：把 Eidon 的数据目录挂进 HeyGem 容器，并保证两边路径一致。

编辑 HeyGem 的 `docker-compose.yml`，给 face2face 服务加一行 volume，让容器内路径 == 宿主机路径：

```yaml
services:
  heygem-face2face:        # 服务名以官方实际为准
    volumes:
      - /home/<你的用户名>/Eidon/backend:/home/<你的用户名>/Eidon/backend
```

这样 Eidon 写在 `~/Eidon/backend/avatars/x.mp4`、`~/Eidon/backend/temp/<job>/dubbed_audio.wav` 的文件，容器内用**完全相同的绝对路径**就能读到，路径零翻译。改完 `docker compose up -d` 重起。

> 这是 Eidon ↔ HeyGem 集成最容易出错的地方。若数字人任务报"文件找不到"，99% 是这个挂载没配对。

---

## 6. 端到端验证

1. Windows 浏览器打开 `http://localhost/`（Nginx 80 端口，WSL2 的端口会自动转发到 Windows）
2. 「素材」页上传：一段正面**人脸视频**、一段清晰**参考人声**（记下它说的文字稿）
3. 跑你的核心业务流「口播改写」：贴视频链接 → 选生成条数 → 填风格/角度 → 选人脸视频 → TTS 选 CosyVoice 填参考音色+文字稿 → 提交
4. 任务详情页应看到：转写 → AI 改写 N 条 → 派发 N 个数字人子任务，逐个出片可下载

一键自检四件套是否就绪：
```bash
curl http://127.0.0.1:8000/api/system/tools
# {"ffmpeg":true,"cosyvoice":true,"heygem":true,...}
```

---

## 7. 4090 显存分配 & 排错

**显存(24GB)够同时跑全部**：HeyGem ~8GB + CosyVoice ~4GB + Whisper ~2GB，留有余量。若并发多个数字人任务可能吃紧，串行跑最稳（Eidon 任务队列本就是串行）。

| 症状 | 排查 |
|------|------|
| `nvidia-smi` 在 WSL2 里没输出 | Windows 装的是**普通 Game Ready 驱动**即可，不要在 WSL2 内再装 NVIDIA 驱动；重启 WSL：`wsl --shutdown` |
| 容器跑不了 GPU | 第 2 步的 `--gpus all` 测试是否通过；`nvidia-ctk` 是否配过 |
| 数字人"文件找不到" | 第 5 步的 volume 挂载路径是否两边一致 |
| CosyVoice 装不上 pynini | 必须用 `conda install -c conda-forge pynini`，别用 pip |
| 浏览器打不开 localhost | WSL2 端口转发偶发失效，`wsl --shutdown` 重进；或用 `localhost:8000` 直连后端测 |
| 转写很慢 | 装 CUDA 版 torch（第 3 步备注） |

---

## 8. 开机自启 & 日常操作

- Eidon 后端：`sudo systemctl {status|restart} eidon-backend`，日志 `journalctl -u eidon-backend -f`
- HeyGem：`docker compose {ps|restart|logs}`（在 Duix.Heygem 目录）
- CosyVoice：建议用 `tmux` 或写个 systemd unit 常驻
- 让 WSL2 开机自动起服务：Windows 任务计划程序加一条开机执行 `wsl -d Ubuntu -u root service eidon-backend start`，或在 WSL2 里配 systemd（本指南 setup.sh 已用 systemd）

---

## 与纯 Linux 服务器方案的关系

本指南是 [README.md](README.md)（Ubuntu 裸机版）的 Windows/WSL2 适配版。核心部署逻辑（setup.sh、systemd 单进程约束、Nginx、字体）完全一致，区别只在最外层：Windows 上多了"装 WSL2 + GPU 透传"这一层，之后全部在 WSL2 里就跟 Ubuntu 服务器一模一样。
