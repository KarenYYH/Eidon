import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link2, Wand2, UserSquare2, Film, Play, ChevronRight, ChevronLeft, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useJobStore } from '../../stores/jobStore'
import { listVoices, listVoiceSamples, listAvatars, checkTools } from '../../utils/api'
import type { Voice, AssetFile } from '../../types'

const LANGUAGES = [
  { code: 'zh', label: '中文 (简体)' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'es', label: 'Español' },
]

type OutputKind = 'stock_video' | 'digital_human'

// 一键洗稿向导：链接 → 改写 → 出片方式 → 配音 → 可选项 → 提交
export function WizardPage() {
  const navigate = useNavigate()
  const { submitJob } = useJobStore()

  const [step, setStep] = useState(1)
  const [url, setUrl] = useState('')
  const [scriptCount, setScriptCount] = useState(3)
  const [scriptLang, setScriptLang] = useState('zh')
  const [rewriteStyle, setRewriteStyle] = useState('')
  const [outputKind, setOutputKind] = useState<OutputKind>('stock_video')
  const [avatarVideo, setAvatarVideo] = useState('')
  const [ttsProvider, setTtsProvider] = useState('edge')
  const [voice, setVoice] = useState('')
  const [promptAudio, setPromptAudio] = useState('')
  const [promptText, setPromptText] = useState('')
  const [bgmEnabled, setBgmEnabled] = useState(false)
  const [publishPlatforms, setPublishPlatforms] = useState<string[]>([])

  const [voices, setVoices] = useState<Voice[]>([])
  const [voiceSamples, setVoiceSamples] = useState<AssetFile[]>([])
  const [avatars, setAvatars] = useState<AssetFile[]>([])
  const [tools, setTools] = useState<Record<string, boolean>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listVoices().then(setVoices).catch(() => {})
    listVoiceSamples().then(setVoiceSamples).catch(() => {})
    listAvatars().then(setAvatars).catch(() => {})
    checkTools().then(setTools).catch(() => {})
  }, [])

  const filteredVoices = voices.filter(v => scriptLang === 'zh' ? v.lang.startsWith('zh') : v.lang === scriptLang)
  const stockReady = tools.stock === true

  function next() { setError(''); setStep(s => Math.min(s + 1, 4)) }
  function back() { setError(''); setStep(s => Math.max(s - 1, 1)) }

  function validateStep(): string {
    if (step === 1 && !url.trim()) return '请输入视频链接'
    if (step === 3) {
      if (outputKind === 'digital_human' && !avatarVideo) return '数字人出片需要选择人脸参考视频'
      if (ttsProvider === 'cosyvoice' && (!promptAudio || !promptText.trim())) return '声音克隆需要选择参考音色并填写其文字稿'
    }
    return ''
  }

  function handleNext() {
    const err = validateStep()
    if (err) { setError(err); return }
    next()
  }

  async function handleSubmit() {
    setError('')
    const err = validateStep()
    if (err) { setError(err); return }
    setSubmitting(true)
    try {
      const clone = ttsProvider === 'cosyvoice'
        ? { prompt_audio: promptAudio, prompt_text: promptText } : {}
      const job = await submitJob({
        mode: 'rewrite',
        source_url: url.trim(),
        script_count: scriptCount,
        rewrite_style: rewriteStyle.trim(),
        script_language: scriptLang,
        output_kind: outputKind,
        avatar_video: outputKind === 'digital_human' ? avatarVideo : undefined,
        tts_provider: ttsProvider,
        voice,
        bgm_enabled: bgmEnabled,
        publish_platforms: publishPlatforms,
        ...clone,
      })
      navigate(`/jobs/${job.id}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const steps = ['视频链接', '改写设置', '出片方式', '配音与发布']

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
          <Wand2 className="w-6 h-6 text-brand-400" />一键洗稿
        </h1>
        <p className="text-sm text-zinc-400 mt-1">贴一个视频链接，自动改写口播稿并批量出片</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-8">
        {steps.map((label, i) => (
          <div key={i} className="flex items-center flex-1">
            <div className={clsx('flex items-center gap-2 text-xs',
              i + 1 === step ? 'text-brand-400 font-medium' : i + 1 < step ? 'text-accent-400' : 'text-zinc-600')}>
              <span className={clsx('w-6 h-6 rounded-full flex items-center justify-center border',
                i + 1 === step ? 'border-brand-400 bg-brand-500/20' : i + 1 < step ? 'border-accent-400 bg-accent-500/20' : 'border-surface-500')}>
                {i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </div>
            {i < steps.length - 1 && <div className="flex-1 h-px bg-surface-600 mx-2" />}
          </div>
        ))}
      </div>

      {/* Step 1: link */}
      {step === 1 && (
        <div className="card p-5 space-y-3">
          <label className="text-xs text-zinc-400 mb-1 flex items-center gap-1.5">
            <Link2 className="w-3.5 h-3.5" />要洗稿的视频链接
          </label>
          <input type="url" className="input" placeholder="https://www.youtube.com/watch?v=..."
            value={url} onChange={e => setUrl(e.target.value)} />
          <p className="text-xs text-zinc-600">支持 YouTube、B站、抖音等单个视频直链。将提取其口播稿用于改写。</p>
        </div>
      )}

      {/* Step 2: rewrite settings */}
      {step === 2 && (
        <div className="card p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">生成条数</label>
              <select className="input" value={scriptCount} onChange={e => setScriptCount(Number(e.target.value))}>
                {[1, 2, 3, 5, 8, 10].map(n => <option key={n} value={n}>{n} 条</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">脚本语言</label>
              <select className="input" value={scriptLang} onChange={e => { setScriptLang(e.target.value); setVoice('') }}>
                {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-400 mb-1.5 block">风格 / 角度（可选）</label>
            <input type="text" className="input" placeholder="如：换个开头钩子、第一人称、更口语化、突出卖点"
              value={rewriteStyle} onChange={e => setRewriteStyle(e.target.value)} />
          </div>
          <p className="text-xs text-zinc-600">AI 会基于原口播稿，产出 {scriptCount} 条全新的、可独立成片的口播稿。</p>
        </div>
      )}

      {/* Step 3: output kind */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={() => setOutputKind('stock_video')}
              className={clsx('card p-4 text-left transition-all border',
                outputKind === 'stock_video' ? 'border-brand-400 bg-brand-500/10' : 'border-surface-600 hover:border-surface-400')}>
              <Film className={clsx('w-5 h-5 mb-2', outputKind === 'stock_video' ? 'text-brand-400' : 'text-zinc-400')} />
              <p className="text-sm font-medium text-zinc-200">配音 + 在线素材</p>
              <p className="text-xs text-zinc-500 mt-1">自动配画面，无需 GPU/人脸</p>
            </button>
            <button type="button" onClick={() => setOutputKind('digital_human')}
              className={clsx('card p-4 text-left transition-all border',
                outputKind === 'digital_human' ? 'border-brand-400 bg-brand-500/10' : 'border-surface-600 hover:border-surface-400')}>
              <UserSquare2 className={clsx('w-5 h-5 mb-2', outputKind === 'digital_human' ? 'text-brand-400' : 'text-zinc-400')} />
              <p className="text-sm font-medium text-zinc-200">数字人口播</p>
              <p className="text-xs text-zinc-500 mt-1">真人脸对口型，需 HeyGem + GPU</p>
            </button>
          </div>

          {outputKind === 'stock_video' && !stockReady && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-300/90">
                在线素材未配置：到「设置」填 Pexels/Pixabay key 才能自动配画面。
                未配置时画面会降级为文字卡。
              </p>
            </div>
          )}

          {outputKind === 'digital_human' && (
            <div className="card p-5">
              <label className="text-xs text-zinc-400 mb-1.5 block">人脸参考视频</label>
              <select className="input" value={avatarVideo} onChange={e => setAvatarVideo(e.target.value)}>
                <option value="">选择人脸视频…</option>
                {avatars.map(a => <option key={a.path} value={a.path}>{a.name}</option>)}
              </select>
              {avatars.length === 0 && (
                <p className="text-xs text-amber-500/80 mt-1.5">素材库暂无人脸视频，请到「素材」页上传</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 4: voice + publish */}
      {step === 4 && (
        <div className="space-y-4">
          <div className="card p-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">TTS 引擎</label>
                <select className="input" value={ttsProvider} onChange={e => setTtsProvider(e.target.value)}>
                  <option value="edge">Edge TTS (免费)</option>
                  <option value="cosyvoice">CosyVoice2 (声音克隆)</option>
                </select>
              </div>
              {ttsProvider === 'edge' && filteredVoices.length > 0 && (
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block">声音</label>
                  <select className="input" value={voice} onChange={e => setVoice(e.target.value)}>
                    <option value="">默认</option>
                    {filteredVoices.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                  </select>
                </div>
              )}
            </div>
            {ttsProvider === 'cosyvoice' && (
              <div className="space-y-3 border-t border-surface-600 pt-4">
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block">参考音色（克隆样本）</label>
                  <select className="input" value={promptAudio} onChange={e => setPromptAudio(e.target.value)}>
                    <option value="">选择参考音频…</option>
                    {voiceSamples.map(v => <option key={v.path} value={v.path}>{v.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block">参考音频文字稿</label>
                  <input type="text" className="input" placeholder="参考音频里说的内容（须与音频一致）"
                    value={promptText} onChange={e => setPromptText(e.target.value)} />
                </div>
              </div>
            )}
            {outputKind === 'stock_video' && (
              <label className="flex items-center gap-3 cursor-pointer">
                <div className={clsx('w-9 h-5 rounded-full transition-all relative', bgmEnabled ? 'bg-brand-500' : 'bg-surface-500')}>
                  <div className={clsx('absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all', bgmEnabled ? 'left-4' : 'left-0.5')} />
                </div>
                <input type="checkbox" className="sr-only" checked={bgmEnabled} onChange={e => setBgmEnabled(e.target.checked)} />
                <span className="text-sm text-zinc-300">自动混入背景音乐</span>
              </label>
            )}
          </div>

          <div className="card p-5 space-y-2">
            <p className="text-xs text-zinc-400 font-medium">成片后自动发布（需后端配置 upload-post）</p>
            <div className="flex flex-wrap gap-2">
              {['tiktok', 'instagram', 'youtube', 'facebook'].map(p => {
                const on = publishPlatforms.includes(p)
                return (
                  <button key={p} type="button"
                    onClick={() => setPublishPlatforms(on ? publishPlatforms.filter(x => x !== p) : [...publishPlatforms, p])}
                    className={clsx('px-3 py-1.5 rounded-lg text-xs transition-all',
                      on ? 'bg-brand-500/30 text-brand-300' : 'bg-surface-700 text-zinc-400 hover:text-zinc-200')}>
                    {p}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mt-5">{error}</p>}

      {/* Nav buttons */}
      <div className="flex gap-3 mt-6">
        {step > 1 && (
          <button onClick={back} className="btn-ghost flex items-center gap-1.5">
            <ChevronLeft className="w-4 h-4" />上一步
          </button>
        )}
        {step < 4 ? (
          <button onClick={handleNext} className="btn-primary flex-1 flex items-center justify-center gap-2 py-3">
            下一步<ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button onClick={handleSubmit} disabled={submitting} className="btn-primary flex-1 flex items-center justify-center gap-2 py-3">
            <Play className="w-4 h-4" />{submitting ? '提交中…' : '改写并批量生成'}
          </button>
        )}
      </div>
    </div>
  )
}
