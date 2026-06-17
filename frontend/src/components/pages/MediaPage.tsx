import { useState, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Film, Music, Upload, Trash2, Loader2, Mic, UserSquare2 } from 'lucide-react'
import clsx from 'clsx'
import {
  listMedia, listBGM, uploadMedia, uploadBGM, deleteMediaClip, deleteBGM,
  listVoiceSamples, listAvatars, uploadVoiceSample, uploadAvatar, deleteVoiceSample, deleteAvatar,
} from '../../utils/api'
import type { MediaClip, BGMTrack, AssetFile } from '../../types'

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function MediaPage() {
  const [tab, setTab] = useState<'clips' | 'bgm' | 'voices' | 'avatars'>('clips')
  const [clips, setClips] = useState<MediaClip[]>([])
  const [bgmTracks, setBgmTracks] = useState<BGMTrack[]>([])
  const [voiceSamples, setVoiceSamples] = useState<AssetFile[]>([])
  const [avatars, setAvatars] = useState<AssetFile[]>([])
  const [uploading, setUploading] = useState(false)

  const loadAll = () => {
    listMedia().then(setClips).catch(() => {})
    listBGM().then(setBgmTracks).catch(() => {})
    listVoiceSamples().then(setVoiceSamples).catch(() => {})
    listAvatars().then(setAvatars).catch(() => {})
  }
  useEffect(() => { loadAll() }, [])

  const { getRootProps: getClipProps, getInputProps: getClipInput, isDragActive: clipDrag } = useDropzone({
    accept: { 'video/*': [], 'image/*': [] },
    onDrop: async (files) => {
      setUploading(true)
      for (const f of files) await uploadMedia(f).catch(() => {})
      loadAll(); setUploading(false)
    },
  })

  const { getRootProps: getBGMProps, getInputProps: getBGMInput, isDragActive: bgmDrag } = useDropzone({
    accept: { 'audio/*': [] },
    onDrop: async (files) => {
      setUploading(true)
      for (const f of files) await uploadBGM(f).catch(() => {})
      loadAll(); setUploading(false)
    },
  })

  const { getRootProps: getVoiceProps, getInputProps: getVoiceInput, isDragActive: voiceDrag } = useDropzone({
    accept: { 'audio/*': [] },
    onDrop: async (files) => {
      setUploading(true)
      for (const f of files) await uploadVoiceSample(f).catch(() => {})
      loadAll(); setUploading(false)
    },
  })

  const { getRootProps: getAvatarProps, getInputProps: getAvatarInput, isDragActive: avatarDrag } = useDropzone({
    accept: { 'video/*': [] },
    onDrop: async (files) => {
      setUploading(true)
      for (const f of files) await uploadAvatar(f).catch(() => {})
      loadAll(); setUploading(false)
    },
  })

  return (
    <div className="px-6 py-10 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">素材库</h1>
        <p className="text-sm text-zinc-400 mt-1">管理视频素材和背景音乐，AI 创作模式自动从此处匹配素材</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface-700 rounded-xl p-1 w-fit">
        <button onClick={() => setTab('clips')} className={clsx(
          'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
          tab === 'clips' ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Film className="w-4 h-4" />视频素材 ({clips.length})
        </button>
        <button onClick={() => setTab('bgm')} className={clsx(
          'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
          tab === 'bgm' ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Music className="w-4 h-4" />背景音乐 ({bgmTracks.length})
        </button>
        <button onClick={() => setTab('voices')} className={clsx(
          'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
          tab === 'voices' ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <Mic className="w-4 h-4" />参考音色 ({voiceSamples.length})
        </button>
        <button onClick={() => setTab('avatars')} className={clsx(
          'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
          tab === 'avatars' ? 'bg-surface-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
        )}>
          <UserSquare2 className="w-4 h-4" />人脸视频 ({avatars.length})
        </button>
      </div>

      {tab === 'clips' && (
        <>
          <div {...getClipProps()} className={clsx(
            'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-6 transition-all',
            clipDrag ? 'border-brand-400 bg-brand-500/5' : 'border-surface-500 hover:border-surface-400'
          )}>
            <input {...getClipInput()} />
            {uploading ? <Loader2 className="w-6 h-6 animate-spin text-brand-400 mx-auto" /> : <>
              <Upload className="w-6 h-6 text-zinc-500 mx-auto mb-1.5" />
              <p className="text-sm text-zinc-400">拖拽视频/图片文件上传</p>
              <p className="text-xs text-zinc-600 mt-0.5">支持 mp4 · mov · avi · mkv · jpg · png</p>
            </>}
          </div>
          {clips.length === 0 ? (
            <p className="text-center text-zinc-500 py-12">暂无素材，请上传视频或图片文件</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {clips.map(clip => (
                <div key={clip.name} className="card p-3 flex items-start gap-3">
                  <Film className="w-8 h-8 text-brand-400 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{clip.name}</p>
                    <p className="text-xs text-zinc-500">{clip.type} · {formatSize(clip.size)}</p>
                  </div>
                  <button onClick={() => deleteMediaClip(clip.name).then(loadAll)} className="text-zinc-600 hover:text-red-400 transition-colors shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'bgm' && (
        <>
          <div {...getBGMProps()} className={clsx(
            'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-6 transition-all',
            bgmDrag ? 'border-brand-400 bg-brand-500/5' : 'border-surface-500 hover:border-surface-400'
          )}>
            <input {...getBGMInput()} />
            {uploading ? <Loader2 className="w-6 h-6 animate-spin text-brand-400 mx-auto" /> : <>
              <Upload className="w-6 h-6 text-zinc-500 mx-auto mb-1.5" />
              <p className="text-sm text-zinc-400">拖拽音频文件上传</p>
              <p className="text-xs text-zinc-600 mt-0.5">支持 mp3 · wav · m4a · aac</p>
            </>}
          </div>
          {bgmTracks.length === 0 ? (
            <p className="text-center text-zinc-500 py-12">暂无背景音乐，请上传音频文件</p>
          ) : (
            <div className="space-y-2">
              {bgmTracks.map(track => (
                <div key={track.name} className="card px-4 py-3 flex items-center gap-3">
                  <Music className="w-5 h-5 text-accent-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{track.name}</p>
                    <p className="text-xs text-zinc-500">{formatSize(track.size)}</p>
                  </div>
                  <button onClick={() => deleteBGM(track.name).then(loadAll)} className="text-zinc-600 hover:text-red-400 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'voices' && (
        <>
          <div {...getVoiceProps()} className={clsx(
            'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-6 transition-all',
            voiceDrag ? 'border-brand-400 bg-brand-500/5' : 'border-surface-500 hover:border-surface-400'
          )}>
            <input {...getVoiceInput()} />
            {uploading ? <Loader2 className="w-6 h-6 animate-spin text-brand-400 mx-auto" /> : <>
              <Upload className="w-6 h-6 text-zinc-500 mx-auto mb-1.5" />
              <p className="text-sm text-zinc-400">拖拽参考音频上传（用于 CosyVoice 声音克隆）</p>
              <p className="text-xs text-zinc-600 mt-0.5">支持 wav · mp3 · m4a · flac，建议 5-15 秒清晰人声</p>
            </>}
          </div>
          {voiceSamples.length === 0 ? (
            <p className="text-center text-zinc-500 py-12">暂无参考音色，请上传一段清晰人声样本</p>
          ) : (
            <div className="space-y-2">
              {voiceSamples.map(v => (
                <div key={v.name} className="card px-4 py-3 flex items-center gap-3">
                  <Mic className="w-5 h-5 text-accent-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{v.name}</p>
                    <p className="text-xs text-zinc-500">{formatSize(v.size)}</p>
                  </div>
                  <button onClick={() => deleteVoiceSample(v.name).then(loadAll)} className="text-zinc-600 hover:text-red-400 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'avatars' && (
        <>
          <div {...getAvatarProps()} className={clsx(
            'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-6 transition-all',
            avatarDrag ? 'border-brand-400 bg-brand-500/5' : 'border-surface-500 hover:border-surface-400'
          )}>
            <input {...getAvatarInput()} />
            {uploading ? <Loader2 className="w-6 h-6 animate-spin text-brand-400 mx-auto" /> : <>
              <Upload className="w-6 h-6 text-zinc-500 mx-auto mb-1.5" />
              <p className="text-sm text-zinc-400">拖拽人脸视频上传（用于 HeyGem 数字人）</p>
              <p className="text-xs text-zinc-600 mt-0.5">支持 mp4 · mov · webm，建议正面清晰人脸</p>
            </>}
          </div>
          {avatars.length === 0 ? (
            <p className="text-center text-zinc-500 py-12">暂无人脸视频，请上传一段正面人脸视频</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {avatars.map(a => (
                <div key={a.name} className="card p-3 flex items-start gap-3">
                  <UserSquare2 className="w-8 h-8 text-brand-400 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{a.name}</p>
                    <p className="text-xs text-zinc-500">{formatSize(a.size)}</p>
                  </div>
                  <button onClick={() => deleteAvatar(a.name).then(loadAll)} className="text-zinc-600 hover:text-red-400 transition-colors shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
