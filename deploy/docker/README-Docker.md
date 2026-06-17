# Eidon 全栈 Docker 部署（最省心，推荐给「只想用」的人）

用 Docker 一条命令起 Eidon，**不用碰 WSL 命令、不用装 conda、不用配 systemd**。
适合给别人用：装个 Docker Desktop，填一个 key，`up -d` 就能用。

> **本文档是 Phase 1**：覆盖 Eidon 核心功能 —— 下载→转写→AI 改写→**免费 edge 配音**→
> 烧字幕→出片。数字人(HeyGem)和声音克隆(CosyVoice)需要 GPU，作为 Phase 2/3 后续接入
> （见文末）。只要核心功能的话，Phase 1 就够，且**不需要 GPU**。

---

## 0. 准备（一次性）

1. 装 **Docker Desktop**
   - Windows：官网下载安装，安装时勾选 **使用 WSL2 引擎**（默认即是）。装完它自己管 WSL，
     你不用手敲任何 wsl 命令。
   - macOS / Linux：装 Docker Desktop 或 Docker Engine 即可。
2. 准备一个 **LLM API Key**（翻译/改写用，推荐 DeepSeek）。

---

## 1. 部署（三步）

```bash
# 1) 进入 docker 目录
cd Eidon/deploy/docker

# 2) 复制环境模板并填 key
cp .env.docker.example .env
#   编辑 .env，至少填 LLM_API_KEY；DeepSeek 用户 LLM_BASE_URL/LLM_MODEL 已默认好

# 3) 构建并启动（国内网络在前面加 CN=1 显著加速）
docker compose up -d --build
#   国内：CN=1 docker compose build && docker compose up -d
```

构建首次较慢（装 ffmpeg + Python 依赖含 torch）。完成后：

```bash
docker compose ps                                  # backend / frontend 都 Up
curl http://localhost:8000/api/system/health       # 直连后端（若没映射 8000 见下）
```

浏览器打开 **http://localhost/** 就能看到界面。

> 默认只把前端 80 端口对外暴露，后端 8000 仅在 compose 网络内（由前端反代 /api）。
> 想直连后端调试，在 `docker-compose.yml` 的 backend 下取消 `ports: 8000:8000` 注释。

---

## 2. 国内加速

构建阶段把 apt / pip / npm 切到国内镜像，传 `CN=1` 即可：

```bash
CN=1 docker compose build      # 构建走清华 pip/apt + npmmirror
docker compose up -d
```

镜像体积较大（含 torch），首次拉基础镜像也可能慢。若反复部署多台，可配合
[README-Offline.md](README-Offline.md) 把镜像 `docker save`/`load` 离线搬运。

---

## 3. 用起来

1. 浏览器开 http://localhost/
2. 「素材」页可上传本地视频/素材
3. 跑翻译 / 创作 / 口播改写任务：转写→AI 改写→edge 配音→烧字幕→出片可下载
4. 查依赖与外部服务状态：
   ```bash
   curl http://localhost:8000/api/system/tools     # ffmpeg=true 即核心就绪
   ```

数据持久化在 Docker 命名卷里（`docker volume ls` 可见 `docker_eidon-*`、`docker_whisper-cache`）。
Whisper 模型下载一次后缓存在 `whisper-cache` 卷，重建容器不重下。

---

## 4. 日常运维

```bash
docker compose logs -f backend          # 看后端日志
docker compose restart backend          # 改 .env 后重启生效
docker compose down                     # 停（保留数据卷）
docker compose down -v                  # 停并删数据卷（慎用，会清空成片/素材/模型）
docker compose up -d --build            # 更新代码后重建
```

**关键约束**：backend 必须**单进程**（任务队列是进程内单例）。不要给 backend 加副本或
`--workers`，否则任务会丢。

---

## 5. 后续 Phase（数字人 / 声音克隆，需 GPU）

Phase 1 不含这两项。它们需要 NVIDIA GPU + 容器 GPU 透传，将作为后续接入：

- **Phase 2 — HeyGem 数字人**：在 compose 加 `heygem` 服务（端口 8383，GPU）。
  关键约束：backend 与 heygem 必须**共享同一卷且容器内路径一致**，因为 Eidon 把
  音频/人脸视频的绝对路径传给 HeyGem，HeyGem 要按同一路径读到。`.env` 设
  `HEYGEM_HOST=http://heygem:8383`。
- **Phase 3 — CosyVoice 声音克隆**：加 `cosyvoice` 服务（端口 50000，GPU），
  `.env` 设 `COSYVOICE_HOST=http://cosyvoice:50000`、`TTS_PROVIDER=cosyvoice`。

`docker-compose.yml` 底部已留好这两段的扩展位注释。

> 不想等 Docker 化数字人？现有的 [README-Windows.md](README-Windows.md)（WSL2 全套 +
> 一键脚本）已能跑完整的数字人 + 声音克隆，是另一条并行的成熟路径。
