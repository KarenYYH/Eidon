# Eidon — AI Video Studio

AI 视频全流程处理平台。四种工作模式：

- **翻译配音**：视频链接/文件 → 转写 → 翻译 → 配音 → 烧字幕合成
- **AI 创作**：主题 → 生成分镜脚本 → 配音 → 匹配/下载素材 → 合成
- **数字人**：文稿 → 配音（可声音克隆）→ HeyGem 口型同步
- **口播改写**：视频链接 → 提取口播稿 → AI 改写成 N 条 → 批量生成 N 个数字人视频

## 技术栈

- **后端**: Python + FastAPI + asyncio 任务队列 + WebSocket 进度推送
- **前端**: React 18 + Vite + Tailwind CSS (暗色主题)
- **AI 工具**: Whisper (ASR) · OpenAI 兼容 LLM/DeepSeek (翻译/改写/脚本) · EdgeTTS/CosyVoice2 (TTS·声音克隆) · HeyGem (数字人口型)
- **媒体处理**: yt-dlp (下载) · FFmpeg (合成/字幕/转场) · Pexels/Pixabay (在线素材) · upload-post (多平台发布)

## 快速启动

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 启动

```bash
./start.sh
```

然后访问 http://localhost:5173

## 可选集成 / 增强

| 能力 | 依赖 | 配置 |
|------|------|------|
| 声音克隆 TTS | CosyVoice2（GPU 服务，端口 50000） | `git clone FunAudioLLM/CosyVoice` 起服务；`.env` 设 `TTS_PROVIDER=cosyvoice`、`COSYVOICE_HOST` |
| 数字人口型 | HeyGem（Docker/GPU，端口 8383） | `git clone duixcom/Duix.Heygem` 起服务；`.env` 设 `HEYGEM_HOST` |
| 在线素材自动下载 | Pexels / Pixabay（免费云 API） | `.env` 设 `STOCK_ENABLED=true` + `PEXELS_API_KEY` 或 `PIXABAY_API_KEY` |
| 多平台自动发布 | upload-post.com（云 API） | `.env` 设 `UPLOAD_POST_API_KEY`，并在其后台授权社交账号 |

> 字幕样式（位置/字号/颜色/描边）、画幅（9:16/16:9/1:1）、拼接顺序、转场、BGM 音量均为内置能力，无需外部依赖，新建任务的「高级设置」里可调。

**生产部署**：
- Linux GPU 服务器 → [deploy/README.md](deploy/README.md)（脚本 + systemd + Nginx，含各服务/Key 申请步骤）
- Windows + RTX 4090 → [deploy/README-Windows.md](deploy/README-Windows.md)（WSL2 全套，复用 Linux 脚本）

## 目录结构

```
Eidon/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── core/                # 配置、任务管理器（内存单例队列）
│   ├── api/routes/          # tasks / jobs / system / media / assets 路由
│   ├── services/
│   │   ├── downloader/      # yt-dlp 下载
│   │   ├── transcriber/     # Whisper ASR
│   │   ├── translator/      # LLM 翻译
│   │   ├── script/          # 脚本生成 + 口播稿改写(rewriter) + 场景拼接
│   │   ├── tts/             # EdgeTTS / CosyVoice 声音克隆
│   │   ├── lipsync/         # HeyGem 数字人
│   │   ├── media/           # 本地素材库 + 在线素材(stock) + 数字人资产
│   │   ├── publish/         # upload-post 多平台发布
│   │   ├── synthesizer/     # FFmpeg 合成/字幕/BGM
│   │   └── pipeline.py      # 四种模式处理流水线
│   ├── models/              # Pydantic 数据模型
│   └── tests/               # pytest 测试（95 个，python3 -m pytest）
├── frontend/
│   └── src/
│       ├── components/      # React 组件（4 种任务模式 + 素材/设置页）
│       ├── stores/          # Zustand 状态
│       ├── types/           # TypeScript 类型
│       └── utils/           # API 客户端
└── deploy/                  # 生产部署脚本与文档
```

