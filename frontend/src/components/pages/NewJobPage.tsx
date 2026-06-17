import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Link2, Upload, Settings2, Play, Sparkles, Music, UserSquare2, Copy } from 'lucide-react'
import clsx from 'clsx'
import { useJobStore } from '../../stores/jobStore'
import { listVoices, listVoiceSamples, listAvatars } from '../../utils/api'
import type { Voice, AssetFile } from '../../types'

const LANGUAGES = [
  { code: 'zh', label: '中文 (简体)' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'es', label: 'Español' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
]

const DURATIONS = [30, 60, 90, 120]

export function NewJobPage() {
  const navigate = useNavigate()
  const { submitJob, submitUpload } = useJobStore()

  const [pageMode, setPageMode] = useState<'translate' | 'create' | 'digital_human' | 'rewrite'>('translate')
  // translate mode
  const [inputMode, setInputMode] = useState<'url' | 'file'>('url')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [targetLang, setTargetLang] = useState('zh')
  // create mode
  const [topic, setTopic] = useState('')
  const [durationSec, setDurationSec] = useState(60)
  const [scriptLang, setScriptLang] = useState('zh')
  // digital-human mode
  const [dhText, setDhText] = useState('')
  const [avatarVideo, setAvatarVideo] = useState('')
  // rewrite (batch) mode
  const [rewriteUrl, setRewriteUrl] = useState('')
  const [scriptCount, setScriptCount] = useState(3)
  const [rewriteStyle, setRewriteStyle] = useState('')
  // common
  const [ttsProvider, setTtsProvider] = useState('edge')
  const [voice, setVoice] = useState('')
  const [bgmEnabled, setBgmEnabled] = useState(false)
  const [bgmVolume, setBgmVolume] = useState(-18)
  const [voices, setVoices] = useState<Voice[]>([])
  // video composition (create mode)
  const [videoAspect, setVideoAspect] = useState('9:16')
  const [concatMode, setConcatMode] = useState('sequential')
  const [transition, setTransition] = useState('none')
  // subtitle style
  const [subPosition, setSubPosition] = useState('bottom')
  const [subFontSize, setSubFontSize] = useState(24)
  const [subColor, setSubColor] = useState('#FFFFFF')
  const [subStrokeColor, setSubStrokeColor] = useState('#000000')
  // publishing
  const [publishPlatforms, setPublishPlatforms] = useState<string[]>([])
  // voice-clone + avatar asset libraries
  const [voiceSamples, setVoiceSamples] = useState<AssetFile[]>([])
  const [avatars, setAvatars] = useState<AssetFile[]>([])
  const [promptAudio, setPromptAudio] = useState('')
  const [promptText, setPromptText] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listVoices().then(setVoices).catch(() => {})
    listVoiceSamples().then(setVoiceSamples).catch(() => {})
    listAvatars().then(setAvatars).catch(() => {})
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'video/*': [], 'audio/*': [] },
    maxFiles: 1,
    onDrop: ([f]) => f && setFile(f),
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const clone = ttsProvider === 'cosyvoice'
      ? { prompt_audio: promptAudio, prompt_text: promptText }
      : {}
    const style = {
      bgm_volume_db: bgmVolume,
      subtitle_position: subPosition,
      subtitle_font_size: subFontSize,
      subtitle_color: subColor,
      subtitle_stroke_color: subStrokeColor,
      publish_platforms: publishPlatforms,
    }
    const common = { tts_provider: ttsProvider, voice, bgm_enabled: bgmEnabled, ...clone, ...style }

    setSubmitting(true)
    try {
      if (pageMode === 'create') {
        if (!topic.trim()) { setError('请输入视频主题'); setSubmitting(false); return }
        const job = await submitJob({
          mode: 'create', topic: topic.trim(),
          duration_sec: durationSec, script_language: scriptLang,
          video_aspect: videoAspect, video_concat_mode: concatMode, transition,
          ...common,
        })
        navigate(`/jobs/${job.id}`)
      } else if (pageMode === 'digital_human') {
        if (!dhText.trim()) { setError('请输入数字人文稿'); setSubmitting(false); return }
        if (!avatarVideo) { setError('请选择人脸参考视频'); setSubmitting(false); return }
        if (ttsProvider === 'cosyvoice' && (!promptAudio || !promptText.trim())) {
          setError('声音克隆需要选择参考音色并填写其文字稿'); setSubmitting(false); return
        }
        const job = await submitJob({
          mode: 'digital_human', text: dhText.trim(), avatar_video: avatarVideo, ...common,
        })
        navigate(`/jobs/${job.id}`)
      } else if (pageMode === 'rewrite') {
        if (!rewriteUrl.trim()) { setError('请输入视频链接'); setSubmitting(false); return }
        if (!avatarVideo) { setError('请选择人脸参考视频'); setSubmitting(false); return }
        if (ttsProvider === 'cosyvoice' && (!promptAudio || !promptText.trim())) {
          setError('声音克隆需要选择参考音色并填写其文字稿'); setSubmitting(false); return
        }
        const job = await submitJob({
          mode: 'rewrite', source_url: rewriteUrl.trim(),
          script_count: scriptCount, rewrite_style: rewriteStyle.trim(),
          script_language: scriptLang, avatar_video: avatarVideo, ...common,
        })
        navigate(`/jobs/${job.id}`)
      } else {
        if (inputMode === 'url') {
          if (!url.trim()) { setError('请输入视频链接'); setSubmitting(false); return }
          const job = await submitJob({ mode: 'translate', source_url: url.trim(), target_language: targetLang, ...common })
          navigate(`/jobs/${job.id}`)
        } else {
          if (!file) { setError('请上传视频文件'); setSubmitting(false); return }
          const job = await submitUpload(file, { target_language: targetLang, tts_provider: ttsProvider, voice, bgm_enabled: bgmEnabled })
          navigate(`/jobs/${job.id}`)
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || '提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const voiceLang = (pageMode === 'create' || pageMode === 'rewrite') ? scriptLang : targetLang
  const filteredVoices = voices.filter(v => voiceLang === 'zh' ? v.lang.startsWith('zh') : v.lang === voiceLang)

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">新建任务</h1>
        <p className="text-sm text-zinc-400 mt-1">翻译现有视频，或用 AI 从主题生成视频</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 mb-6 bg-surface-700 rounded-xl p-1">
        <button onClick={() => setPageMode('translate')} className={clsx(
          'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
          pageMode === 'translate' ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Link2 className="w-4 h-4" />翻译配音
        </button>
        <button onClick={() => setPageMode('create')} className={clsx(
          'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
          pageMode === 'create' ? 'bg-brand-500/30 text-brand-300' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Sparkles className="w-4 h-4" />AI 创作
        </button>
        <button onClick={() => setPageMode('digital_human')} className={clsx(
          'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
          pageMode === 'digital_human' ? 'bg-brand-500/30 text-brand-300' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <UserSquare2 className="w-4 h-4" />数字人
        </button>
        <button onClick={() => setPageMode('rewrite')} className={clsx(
          'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
          pageMode === 'rewrite' ? 'bg-brand-500/30 text-brand-300' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Copy className="w-4 h-4" />口播改写
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Translate mode source */}
        {pageMode === 'translate' && (
          <div className="card p-5">
            <div className="flex gap-1 mb-4 bg-surface-700 rounded-lg p-0.5 w-fit">
              {(['url', 'file'] as const).map(m => (
                <button key={m} type="button" onClick={() => setInputMode(m)}
                  className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-all',
                    inputMode === m ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200')}>
                  {m === 'url' ? <Link2 className="w-3.5 h-3.5" /> : <Upload className="w-3.5 h-3.5" />}
                  {m === 'url' ? '视频链接' : '本地文件'}
                </button>
              ))}
            </div>
            {inputMode === 'url' ? (
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">视频 URL</label>
                <input type="url" className="input" placeholder="https://www.youtube.com/watch?v=..." value={url} onChange={e => setUrl(e.target.value)} />
                <p className="text-xs text-zinc-600 mt-1.5">支持 YouTube、抖音单个视频直链、B站等</p>
              </div>
            ) : (
              <div {...getRootProps()} className={clsx('border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all',
                isDragActive ? 'border-brand-400 bg-brand-500/5' : 'border-surface-500 hover:border-surface-400')}>
                <input {...getInputProps()} />
                <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
                {file ? <p className="text-sm text-zinc-300">{file.name}</p> : <>
                  <p className="text-sm text-zinc-400">拖拽视频文件到此处</p>
                  <p className="text-xs text-zinc-600 mt-1">或点击选择文件</p>
                </>}
              </div>
            )}
          </div>
        )}

        {/* Create mode */}
        {pageMode === 'create' && (
          <div className="card p-5 space-y-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">视频主题</label>
              <input type="text" className="input" placeholder="如：人工智能如何改变教育行业" value={topic} onChange={e => setTopic(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">视频时长</label>
                <select className="input" value={durationSec} onChange={e => setDurationSec(Number(e.target.value))}>
                  {DURATIONS.map(d => <option key={d} value={d}>{d} 秒</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">脚本语言</label>
                <select className="input" value={scriptLang} onChange={e => { setScriptLang(e.target.value); setVoice('') }}>
                  {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </div>
            </div>
            <p className="text-xs text-zinc-600">AI 将自动生成分镜脚本，并从本地素材库匹配画面</p>
          </div>
        )}

        {/* Digital-human mode */}
        {pageMode === 'digital_human' && (
          <div className="card p-5 space-y-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">数字人文稿</label>
              <textarea className="input min-h-[100px] resize-y" placeholder="输入数字人要说的内容…"
                value={dhText} onChange={e => setDhText(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">人脸参考视频</label>
              <select className="input" value={avatarVideo} onChange={e => setAvatarVideo(e.target.value)}>
                <option value="">选择人脸视频…</option>
                {avatars.map(a => <option key={a.path} value={a.path}>{a.name}</option>)}
              </select>
              {avatars.length === 0 && (
                <p className="text-xs text-amber-500/80 mt-1.5">素材库暂无人脸视频，请到「素材」页上传</p>
              )}
            </div>
            <p className="text-xs text-zinc-600">合成会说话的数字人，需后端配置好 HeyGem 服务</p>
          </div>
        )}

        {/* Rewrite (batch) mode */}
        {pageMode === 'rewrite' && (
          <div className="card p-5 space-y-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">视频链接</label>
              <input type="url" className="input" placeholder="https://..." value={rewriteUrl} onChange={e => setRewriteUrl(e.target.value)} />
              <p className="text-xs text-zinc-600 mt-1.5">将提取视频口播稿，AI 改写后逐条生成数字人视频</p>
            </div>
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
              <input type="text" className="input" placeholder="如：换个开头钩子、第一人称、更口语化、突出卖点" value={rewriteStyle} onChange={e => setRewriteStyle(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">人脸参考视频</label>
              <select className="input" value={avatarVideo} onChange={e => setAvatarVideo(e.target.value)}>
                <option value="">选择人脸视频…</option>
                {avatars.map(a => <option key={a.path} value={a.path}>{a.name}</option>)}
              </select>
              {avatars.length === 0 && (
                <p className="text-xs text-amber-500/80 mt-1.5">素材库暂无人脸视频，请到「素材」页上传</p>
              )}
            </div>
            <p className="text-xs text-zinc-600">每条改写稿生成一个独立数字人任务，需后端配置好 HeyGem 服务</p>
          </div>
        )}

        {/* Common settings */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm text-zinc-300 font-medium">
            <Settings2 className="w-4 h-4" />配音设置
          </div>
          {pageMode === 'translate' && (
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">目标语言</label>
              <select className="input" value={targetLang} onChange={e => { setTargetLang(e.target.value); setVoice('') }}>
                {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-zinc-400 mb-1.5 block">TTS 引擎</label>
              <select className="input" value={ttsProvider} onChange={e => setTtsProvider(e.target.value)}>
                <option value="edge">Edge TTS (免费)</option>
                <option value="cosyvoice">CosyVoice2 (本地)</option>
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

          {/* CosyVoice zero-shot clone: reference sample + its transcript */}
          {ttsProvider === 'cosyvoice' && (
            <div className="space-y-3 border-t border-surface-600 pt-4">
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">参考音色（克隆样本）</label>
                <select className="input" value={promptAudio} onChange={e => setPromptAudio(e.target.value)}>
                  <option value="">选择参考音频…</option>
                  {voiceSamples.map(v => <option key={v.path} value={v.path}>{v.name}</option>)}
                </select>
                {voiceSamples.length === 0 && (
                  <p className="text-xs text-amber-500/80 mt-1.5">素材库暂无参考音色，请到「素材」页上传</p>
                )}
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1.5 block">参考音频文字稿</label>
                <input type="text" className="input" placeholder="参考音频里说的内容（须与音频一致）"
                  value={promptText} onChange={e => setPromptText(e.target.value)} />
              </div>
            </div>
          )}
          {pageMode !== 'digital_human' && pageMode !== 'rewrite' && (
            <label className="flex items-center gap-3 cursor-pointer">
              <div className={clsx('w-9 h-5 rounded-full transition-all relative', bgmEnabled ? 'bg-brand-500' : 'bg-surface-500')}>
                <div className={clsx('absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all', bgmEnabled ? 'left-4' : 'left-0.5')} />
              </div>
              <input type="checkbox" className="sr-only" checked={bgmEnabled} onChange={e => setBgmEnabled(e.target.checked)} />
              <span className="text-sm text-zinc-300 flex items-center gap-1.5">
                <Music className="w-3.5 h-3.5 text-zinc-400" />
                自动混入背景音乐
              </span>
            </label>
          )}
        </div>

        {/* Advanced settings (collapsible) */}
        <div className="card p-5">
          <button type="button" onClick={() => setShowAdvanced(v => !v)}
            className="flex items-center gap-2 text-sm text-zinc-300 font-medium w-full">
            <Settings2 className="w-4 h-4" />高级设置
            <span className="text-xs text-zinc-500 ml-auto">{showAdvanced ? '收起' : '展开'}</span>
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-5">
              {/* Subtitle style — translate mode burns subtitles */}
              {pageMode === 'translate' && (
                <div className="space-y-3">
                  <p className="text-xs text-zinc-400 font-medium">字幕样式</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">位置</label>
                      <select className="input" value={subPosition} onChange={e => setSubPosition(e.target.value)}>
                        <option value="bottom">底部</option>
                        <option value="center">居中</option>
                        <option value="top">顶部</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">字号</label>
                      <input type="number" className="input" value={subFontSize} min={12} max={72}
                        onChange={e => setSubFontSize(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">文字颜色</label>
                      <input type="color" className="input h-10 p-1" value={subColor} onChange={e => setSubColor(e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">描边颜色</label>
                      <input type="color" className="input h-10 p-1" value={subStrokeColor} onChange={e => setSubStrokeColor(e.target.value)} />
                    </div>
                  </div>
                </div>
              )}

              {/* Video composition — create mode */}
              {pageMode === 'create' && (
                <div className="space-y-3">
                  <p className="text-xs text-zinc-400 font-medium">画面合成</p>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">画幅</label>
                      <select className="input" value={videoAspect} onChange={e => setVideoAspect(e.target.value)}>
                        <option value="9:16">竖屏 9:16</option>
                        <option value="16:9">横屏 16:9</option>
                        <option value="1:1">方形 1:1</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">拼接</label>
                      <select className="input" value={concatMode} onChange={e => setConcatMode(e.target.value)}>
                        <option value="sequential">顺序</option>
                        <option value="random">随机</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 mb-1 block">转场</label>
                      <select className="input" value={transition} onChange={e => setTransition(e.target.value)}>
                        <option value="none">无</option>
                        <option value="fade">淡入淡出</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* BGM volume — only when BGM enabled */}
              {bgmEnabled && pageMode !== 'digital_human' && pageMode !== 'rewrite' && (
                <div>
                  <label className="text-xs text-zinc-400 font-medium mb-1 block">背景音乐音量：{bgmVolume} dB</label>
                  <input type="range" className="w-full" min={-40} max={0} step={1}
                    value={bgmVolume} onChange={e => setBgmVolume(Number(e.target.value))} />
                </div>
              )}

              {/* Publishing */}
              <div className="space-y-2">
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
        </div>

        {error && <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}

        <button type="submit" disabled={submitting} className="btn-primary w-full flex items-center justify-center gap-2 py-3">
          <Play className="w-4 h-4" />
          {submitting ? '提交中…' : pageMode === 'create' ? 'AI 生成视频' : pageMode === 'digital_human' ? '生成数字人' : pageMode === 'rewrite' ? '改写并批量生成' : '开始处理'}
        </button>
      </form>
    </div>
  )
}
