import axios from 'axios'
import type { Job, CreateJobPayload, Voice, LLMConfig, MediaClip, BGMTrack, AssetFile } from '../types'

const api = axios.create({ baseURL: '/api' })

// Jobs
export const createJob = (payload: CreateJobPayload) =>
  api.post<Job>('/tasks', payload).then(r => r.data)

export const uploadAndCreateJob = (
  file: File,
  payload: Omit<CreateJobPayload, 'source_url' | 'mode'> & { target_language: string }
) => {
  const form = new FormData()
  form.append('file', file)
  form.append('target_language', payload.target_language)
  form.append('tts_provider', payload.tts_provider)
  form.append('voice', payload.voice)
  form.append('bgm_enabled', String(payload.bgm_enabled))
  return api.post<Job>('/tasks/upload', form).then(r => r.data)
}

export const listJobs = () =>
  api.get<Job[]>('/tasks').then(r => r.data)

export const getJob = (id: string) =>
  api.get<Job>(`/tasks/${id}`).then(r => r.data)

export const listJobChildren = (id: string) =>
  api.get<Job[]>(`/tasks/${id}/children`).then(r => r.data)

export const cancelJob = (id: string) =>
  api.delete(`/tasks/${id}`).then(r => r.data)

// System
export const listVoices = () =>
  api.get<Voice[]>('/system/voices').then(r => r.data)

export const checkHealth = () =>
  api.get('/system/health').then(r => r.data)

export const checkTools = () =>
  api.get<Record<string, boolean>>('/system/tools').then(r => r.data)

// LLM Config
export const getLLMConfig = () =>
  api.get<LLMConfig>('/system/config').then(r => r.data)

export const saveLLMConfig = (payload: { api_key: string; base_url?: string; model?: string }) =>
  api.post('/system/config', payload).then(r => r.data)

export const testLLM = (payload: { api_key: string; base_url?: string; model?: string }) =>
  api.post<{ status: string; reply?: string; message?: string }>('/system/test-llm', payload).then(r => r.data)

// Media
export const listMedia = () =>
  api.get<MediaClip[]>('/media/clips').then(r => r.data)

export const listBGM = () =>
  api.get<BGMTrack[]>('/media/bgm').then(r => r.data)

export const uploadMedia = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<MediaClip>('/media/upload/clip', form).then(r => r.data)
}

export const uploadBGM = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<BGMTrack>('/media/upload/bgm', form).then(r => r.data)
}

export const deleteMediaClip = (filename: string) =>
  api.delete(`/media/clip/${filename}`).then(r => r.data)

export const deleteBGM = (filename: string) =>
  api.delete(`/media/bgm/${filename}`).then(r => r.data)

// Digital-human assets (voice-clone samples + avatar face videos)
export const listVoiceSamples = () =>
  api.get<AssetFile[]>('/assets/voices').then(r => r.data)

export const listAvatars = () =>
  api.get<AssetFile[]>('/assets/avatars').then(r => r.data)

export const uploadVoiceSample = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<AssetFile>('/assets/upload/voice', form).then(r => r.data)
}

export const uploadAvatar = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<AssetFile>('/assets/upload/avatar', form).then(r => r.data)
}

export const deleteVoiceSample = (filename: string) =>
  api.delete(`/assets/voice/${filename}`).then(r => r.data)

export const deleteAvatar = (filename: string) =>
  api.delete(`/assets/avatar/${filename}`).then(r => r.data)

// WebSocket
export function createJobWebSocket(jobId: string, onMessage: (job: Job) => void) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/api/jobs/${jobId}/ws`)
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (!data.ping) onMessage(data as Job)
  }
  return ws
}
