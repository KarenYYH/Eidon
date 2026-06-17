# Eidon 离线预置指南（多台 / 反复部署）

适用场景：要给**多台机器**装，或同一台**反复重装**。把几个大文件在一台网络好的机器上
**提前下好**，做成可拷贝的本地文件夹/文件，目标机安装时直接用本地内容，不再联网拉。

> 核心权衡：离线预置不减少总下载量，只是把下载**挪到一次、复用 N 次**。
> 单机只装一次，用 `install-wsl-full.sh --cn`（国内镜像）通常就够，不必做离线包。

## 一键打包：prepare-offline.sh（推荐）

不想逐项手动准备？在**准备机**（联网、与目标机同架构/Python 版本，都用 WSL2 Ubuntu 22.04 最稳）跑：

```bash
cd Eidon/deploy
bash prepare-offline.sh --cn             # 国内镜像下载，打包全部五项到 ./eidon-offline
bash prepare-offline.sh --cn --out ~/pkg # 指定输出目录
bash prepare-offline.sh --only models    # 只打某项：heygem|models|wheels|miniconda
bash prepare-offline.sh --whisper medium # 指定 Whisper 模型大小（默认读 .env，没有则 small）
```

它会把下面五项下好、打成可拷贝的 `eidon-offline/` 目录（含 `MANIFEST.txt` 清单），
拷到目标机后按本文档对应章节安装即可。每项可独立重跑，已存在默认跳过（`--force` 重做）。

> 下面各章节是**手动准备**的细节 / 排错参考。用了上面的脚本就不必逐条手敲，
> 但目标机**怎么用**这些本地文件，仍看各章节的「目标机」部分。

---

## 各项明细

下面按**收益从大到小**排。每项都标了：在「准备机」做什么 → 拷什么 → 目标机怎么用。

建议在准备机建一个目录统一放，例如 `eidon-offline/`，整体拷到目标机（U 盘/局域网/网盘）：

```
eidon-offline/
├── heygem-images.tar        # HeyGem 镜像（最大头，~30GB）
├── models/
│   ├── CosyVoice2-0.5B/      # CosyVoice 模型目录
│   └── whisper/small.pt      # Whisper 模型
├── wheels/                   # Python 依赖（含 torch）
└── Miniconda3-latest-Linux-x86_64.sh
```

---

## 1. HeyGem Docker 镜像（~30GB，最值得预置）

数字人镜像是整个安装最大的下载。用 Docker 自带的 save/load 离线搬运。

**准备机（有 Docker、网络好）：**
```bash
# 先按官方 compose 把镜像拉下来（或只 pull 用到的几个 tag）
cd Duix.Heygem
docker compose pull                       # 拉取 compose 里引用的全部镜像
# 看一下都有哪些镜像，把它们打包成一个 tar
docker images
docker save -o heygem-images.tar \
  <镜像1:tag> <镜像2:tag> <镜像3:tag>      # 换成上面 docker images 里 HeyGem 的实际镜像名
```

**目标机：**
```bash
docker load -i heygem-images.tar          # 导入本地镜像
docker images                             # 确认镜像已在本地
# 之后正常跑 install-wsl-full.sh --only heygem
# docker compose up -d 看到镜像已存在，就不会再去网上拉
```

> 关键：`docker load` 后镜像的**名字和 tag 必须与 compose 里写的完全一致**，compose 才会认为"已存在"而跳过拉取。save 前用 `docker images` 抄准名字。

---

## 2. CosyVoice2 模型（~几 GB，天然适合本地目录）

CosyVoice 模型脚本本来就**不自动下载**，启动服务时用 `--model_dir` 指向本地目录即可——
所以提前下好放本地，是它本来就该有的用法。

**准备机：**
```bash
# 方式一：ModelScope（国内快）
pip install modelscope
python -c "from modelscope import snapshot_download; \
  snapshot_download('iic/CosyVoice2-0.5B', local_dir='models/CosyVoice2-0.5B')"

# 方式二：HuggingFace（需可访问 hf.co）
#   huggingface-cli download FunAudioLLM/CosyVoice2-0.5B --local-dir models/CosyVoice2-0.5B
```

**目标机：** 把 `models/CosyVoice2-0.5B` 拷到任意路径，启动时指过去：
```bash
cd ~/CosyVoice/runtime/python/fastapi
python server.py --port 50000 --model_dir /路径/到/models/CosyVoice2-0.5B
```

---

## 3. Whisper 模型（~0.5–1.5GB，放进缓存目录即命中）

Eidon 用的是 **openai-whisper**（`whisper.load_model("small")`），首次转写才下模型。
模型缓存在 `~/.cache/whisper/`，文件名就是 `<模型名>.pt`（如 `small.pt`、`medium.pt`）。
把文件提前放进该目录，运行时直接命中、不联网。

**准备机：** 触发一次下载，或直接下 `.pt`：
```bash
python -c "import whisper; whisper.load_model('small')"   # 下到 ~/.cache/whisper/small.pt
cp ~/.cache/whisper/small.pt models/whisper/
```
（模型名要与目标机 `backend/.env` 里的 `WHISPER_MODEL` 一致，默认 `small`。）

**目标机：**
```bash
mkdir -p ~/.cache/whisper
cp models/whisper/small.pt ~/.cache/whisper/
```

---

## 4. Python 依赖离线包（含 torch，~1–2GB）

把后端所有 pip 依赖（torch 由 openai-whisper 间接带入，是大头）预下成本地 wheels 目录，
目标机纯离线安装。

> 注意：wheel 有平台/Python 版本之分。**准备机的系统架构和 Python 版本要和目标机一致**
> （都用 WSL2 Ubuntu 22.04 + 系统 python3 即可），否则离线装会因找不到匹配 wheel 失败。

**准备机：**
```bash
cd Eidon/backend
pip download -r requirements.txt -d ../../eidon-offline/wheels
```

**目标机：** venv 建好后离线装（不连网）：
```bash
source ~/Eidon/.venv/bin/activate
pip install --no-index --find-links /路径/到/wheels -r ~/Eidon/backend/requirements.txt
```

---

## 5. Miniconda 安装器（CosyVoice 用，~100MB）

CosyVoice 的 pynini 依赖 conda。安装器是单个 `.sh`，直接下好拷过去。

**准备机：**
```bash
curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh \
  -o eidon-offline/Miniconda3-latest-Linux-x86_64.sh
```

**目标机：**
```bash
bash /路径/到/Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
```

> conda 环境本身（pynini 等）不建议跨机搬运——容易因路径/平台损坏。装好 Miniconda 后，
> 用 `--cn` 走清华 conda-forge 镜像装 pynini 即可，那步不大。

---

## 不值得预置的

| 项 | 原因 |
|----|------|
| Docker Engine / NVIDIA Container Toolkit | 体积小，装一次；提前下收益不大 |
| 前端 `node_modules` | 跨机易platform不兼容；换 npmmirror 源更稳（`--cn` 已做） |
| CosyVoice 的 conda 环境整体 | conda env 不好跨机搬，容易坏 |
| apt 系统包 | 依赖关系琐碎，`apt --download-only` 性价比低；`--cn` 换清华源已足够快 |

---

## 完全离线（内网/隔离）补充

若目标机**完全不能联外网**，除上面 1–5 外还要注意：
- Docker Engine、NVIDIA Container Toolkit 的 .deb 也需提前 `apt-get download` 带过去；
- `install-wsl-full.sh` 的多处 `curl`（get.docker.com、nvidia 源等）在无网环境会失败，
  需改为手动按本指南装好各组件后，用 `--only` 跳过已完成阶段、只跑剩余步骤。
- 这种环境建议把本指南当 checklist 手动走，脚本仅作辅助。

> 本指南配合 [README-Windows.md](README-Windows.md) 的快速通道使用：先按本指南把大文件备齐，
> 再跑安装脚本，脚本遇到"已存在/已缓存"会自动跳过对应下载。
