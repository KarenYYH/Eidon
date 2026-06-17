# Eidon 部署指南（Linux GPU 服务器，全部本机）

把 **Eidon 主程序 + CosyVoice2 + HeyGem** 全部部署到同一台带 NVIDIA 显卡的 Linux 服务器。
服务间走 localhost，翻译/改写口播稿走云端 DeepSeek API（不占本地硬件）。

> **Windows + RTX 4090 用户**：改看 [README-Windows.md](README-Windows.md)（WSL2 全套方案，复用本指南的脚本）。

```
┌─────────── 一台 Linux + NVIDIA GPU 服务器 ───────────┐
│  Nginx :80  ── 托管前端静态 + 反代 ↓                  │
│  Eidon 后端 :8000  ── Whisper / ffmpeg / yt-dlp        │
│  CosyVoice2 :50000 (GPU)   ← 声音克隆                  │
│  HeyGem     :8383  (Docker, GPU)  ← 数字人口型          │
└────────────────────────────────────────────────────────┘
```

## 0. 硬件 / 系统要求

| 项 | 最低 | 推荐 |
|----|------|------|
| GPU | NVIDIA 显存 ≥ 8GB | RTX 4090 24GB |
| 内存 | 16GB | 32–64GB |
| 磁盘 | 80GB 空闲 | 150GB+ |
| 系统 | Ubuntu 22.04 + NVIDIA 驱动 + Docker + NVIDIA Container Toolkit | 同左 |

> HeyGem 是显存大户（≥8GB），CosyVoice2 约 4GB。12GB 卡可勉强同跑两者，16GB+ 更稳。

先确认 GPU 可用：
```bash
nvidia-smi               # 看到显卡信息
docker info | grep -i runtime   # 应包含 nvidia（装好 NVIDIA Container Toolkit 后）
```

---

## 1. 部署 Eidon 主程序（本仓库）

```bash
# 把项目拷到服务器后：
cd Eidon/deploy
sudo bash setup.sh
```

脚本会自动完成：装 ffmpeg(带 libass)+Noto CJK 中文字体+Node+Nginx → 建 Python venv 装后端依赖 → 从模板生成 `backend/.env` → `npm run build` 构建前端 → systemd 单进程托管后端 → Nginx 托管前端并反代。

完成后填好 Key 并重启：
```bash
# 编辑 backend/.env，至少填 LLM_API_KEY（DeepSeek）
sudo systemctl restart eidon-backend
```

访问 `http://<服务器IP>/` 即可看到界面。此时 **翻译/创作/口播改写的「前半段」**（下载→转写→AI 改写）已经能跑；数字人出片要继续下面两步。

**关键约束：后端必须单进程**（任务队列是进程内内存单例）。systemd 单元已锁死，不要改成多 worker。

常用运维：
```bash
sudo systemctl status eidon-backend     # 状态
journalctl -u eidon-backend -f          # 实时日志
sudo systemctl restart eidon-backend    # 改 .env 后重启生效
```

---

## 2. 部署 CosyVoice2（声音克隆，端口 50000）

```bash
git clone https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
# 按官方 README 装 conda 环境与依赖、下载 CosyVoice2-0.5B 模型权重
# 启动官方 FastAPI runtime（路径以官方为准）：
cd runtime/python/fastapi
python server.py --port 50000 --model_dir <CosyVoice2-0.5B 模型目录>
```

Eidon 调用的是官方 `POST /inference_zero_shot`（form: `tts_text` / `prompt_text` + file `prompt_wav`），返回 PCM。`.env` 已默认 `COSYVOICE_HOST=http://127.0.0.1:50000`，无需改。

自检：
```bash
curl http://127.0.0.1:50000/    # 有响应即端口通
```

> 不需要声音克隆时，TTS 用默认的 edge（免费云），可跳过本步。

---

## 3. 部署 HeyGem（数字人口型，端口 8383）

```bash
git clone https://github.com/duixcom/Duix.Heygem.git
cd Duix.Heygem
# 按官方 docker-compose 启动（三个镜像约 30GB，需 GPU 容器运行时）
docker compose up -d
```

`.env` 已默认 `HEYGEM_HOST=http://127.0.0.1:8383`。

### ⚠️ 文件共享（最关键的一步）

HeyGem 跑在 Docker 容器里，Eidon 传给它的**音频和人脸视频路径，必须在容器内能访问到**。否则提交任务会报「文件找不到」。两种解法二选一：

- **方案 A（推荐）**：把 Eidon 的数据目录挂载进 HeyGem 容器。在 HeyGem 的 `docker-compose.yml` 给服务加一段卷映射，把 Eidon 项目目录映射到容器内相同路径，例如：
  ```yaml
  volumes:
    - /home/ubuntu/Eidon/backend:/home/ubuntu/Eidon/backend
  ```
  这样 Eidon 传的绝对路径在容器内一致可读。

- **方案 B**：按 HeyGem 官方约定的输入目录放文件（部分版本要求文件先放进它的工作目录），再让 Eidon 写到该目录。

HeyGem 返回结果有两种：可下载 URL，或服务器本地路径。Eidon 两种都已支持（见 `services/lipsync/heygem.py` 的 `_download`）——本地路径方式要求结果文件在 Eidon 进程也能读到（同机即可）。

自检：
```bash
docker compose ps             # 容器都 Up
curl http://127.0.0.1:8383/   # 端口通
```

---

## 3.5 可选增强：在线素材 + 自动发布（按需配置）

这两项是纯云端 API，**不占 GPU、不用部署服务**，只需申请 Key 填进 `backend/.env`，填完 `sudo systemctl restart eidon-backend` 生效。

### A. 在线素材自动下载（Pexels / Pixabay）

作用：AI 创作模式下，本地 `media/` 没有匹配素材时，按场景关键词**自动从免费视频站下载**空镜，补齐画面。二选一即可（也可都填）。

**Pexels（推荐，画质好）**
1. 打开 https://www.pexels.com/api/ ，用邮箱注册并登录
2. 进 "Your API Key" 页面，直接看到一串 key（免费，每月 20000 次请求额度）
3. 填进 `.env`：
   ```ini
   STOCK_ENABLED=true
   STOCK_PROVIDER=pexels
   PEXELS_API_KEY=你的key
   ```

**Pixabay（备选）**
1. 打开 https://pixabay.com/api/docs/ ，注册登录
2. 页面顶部 "Your API key" 处复制 key（免费）
3. 填进 `.env`：
   ```ini
   STOCK_ENABLED=true
   STOCK_PROVIDER=pixabay
   PIXABAY_API_KEY=你的key
   ```

自检（重启后）：
```bash
curl http://127.0.0.1:8000/api/system/tools   # 看到 "stock":true 即配置生效
```

> 不填或 `STOCK_ENABLED=false` 时，创作模式仍按原逻辑：本地有素材就用，没有就文字黑底兜底。

### B. 多平台自动发布（upload-post.com）

作用：成片后一键发到 TikTok / Instagram / YouTube / Facebook 等。

1. 打开 https://www.upload-post.com/ 注册账号
2. 在控制台 **API Keys** 页面创建一个 key
3. 按它的引导**授权绑定**你的目标社交账号（TikTok/IG 等，需在 upload-post 后台 OAuth 授权一次）
4. 填进 `.env`：
   ```ini
   UPLOAD_POST_API_KEY=你的key
   ```

自检：
```bash
curl http://127.0.0.1:8000/api/system/tools   # 看到 "publish":true 即配置生效
```

用法：新建任务时在「高级设置」勾选要发布的平台。**发布失败不影响成片**——视频已生成，只是发布步骤标记失败，可手动重试。

> ⚠️ 这一步会把你的成片**真实上传到第三方服务**并对外发布，请确认内容无误再勾选平台。upload-post 免费额度有限，超量需付费，按官网为准。

---

## 4. 端到端验证

1. 浏览器打开 `http://<服务器IP>/`
2. 「素材」页上传：一段正面**人脸视频**（→人脸视频 Tab）、一段清晰**参考人声**（→参考音色 Tab，记下它说的文字稿）
3. 「口播改写」：贴视频链接 → 选生成条数 → 填风格/角度 → 选人脸视频 →（如用克隆）TTS 选 CosyVoice 并填参考音色+文字稿 → 提交
4. 任务详情页能看到：转写 → AI 改写 N 条 → 派发 N 个数字人子任务，逐个出片可下载

---

## 5. 各环节占用与排错速查

| 环节 | 在哪跑 | 出问题先看 |
|------|--------|-----------|
| 视频下载 | Eidon(yt-dlp) | 链接是否可达；服务器能否访问 YouTube/目标站 |
| 口播稿转文字 | Eidon(Whisper) | `WHISPER_MODEL` 大小；GPU 版 torch 是否装上（加速） |
| 翻译/改写 | DeepSeek 云 API | `LLM_API_KEY`、`LLM_MODEL` 是否正确 |
| 声音克隆 | CosyVoice :50000 | `curl` 端口；模型是否加载；参考音频+文字稿是否提供 |
| 数字人口型 | HeyGem :8383 | 容器是否 Up；**文件共享挂载**；显存是否够 |
| 字幕中文方框 | Eidon(ffmpeg) | `SUBTITLE_FONT` 是否为已安装字体（`fc-list \| grep CJK`） |
| 创作模式没素材/黑屏 | Eidon + 在线素材 | `STOCK_ENABLED=true` + Key；或往 `media/` 放本地素材 |
| 发布失败 | upload-post 云 | `UPLOAD_POST_API_KEY`；社交账号是否已授权绑定；额度是否用尽 |

`/tools` 接口可一键查依赖与外部服务/Key 状态：
```bash
curl http://127.0.0.1:8000/api/system/tools
# {"ffmpeg":true,...,"cosyvoice":true,"heygem":true,"stock":true,"publish":true}
```

---

## 6. 更新版本

```bash
git pull
cd Eidon/deploy && sudo bash setup.sh   # 幂等，会重装依赖+重新构建前端+重启
```
