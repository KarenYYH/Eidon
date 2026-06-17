export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type JobStep = 'download' | 'transcribe' | 'translate' | 'tts' | 'synthesize' | 'script' | 'rewrite' | 'assemble' | 'lipsync' | 'dispatch' | 'publish'
export type JobMode = 'translate' | 'create' | 'digital_human' | 'rewrite'

export interface StepStatus {
  step: JobStep
  status: JobStatus
  progress: number
  message: string
  started_at?: string
  completed_at?: string
  error?: string
}

export interface Job {
  id: string
  title: string
  mode: JobMode
  source_url: string
  source_file?: string
  topic: string
  duration_sec: number
  script_language: string
  scenes: Scene[]
  status: JobStatus
  steps: StepStatus[]
  progress: number
  created_at: string
  updated_at: string
  target_language: string
  tts_provider: string
  voice: string
  bgm_enabled: boolean
  text?: string
  avatar_video?: string
  prompt_audio?: string
  prompt_text?: string
  script_count?: number
  rewrite_style?: string
  scripts?: string[]
  parent_id?: string
  child_ids?: string[]
  video_aspect?: string
  publish_platforms?: string[]
  publish_result?: Record<string, unknown>
  subtitle_file?: string
  audio_file?: string
  output_file?: string
  error?: string
}

export interface Scene {
  narration: string
  visual_keywords: string[]
  duration: number
}

export interface Voice {
  id: string
  name: string
  lang: string
}

export interface LLMConfig {
  api_key_masked: string
  api_key_set: boolean
  base_url: string
  model: string
}

export interface MediaClip {
  name: string
  path: string
  type: 'video' | 'image'
  size: number
}

export interface BGMTrack {
  name: string
  path: string
  size: number
}

export interface AssetFile {
  name: string
  path: string
  size: number
}

export interface CreateJobPayload {
  mode: JobMode
  source_url?: string
  target_language?: string
  topic?: string
  duration_sec?: number
  script_language?: string
  text?: string
  avatar_video?: string
  tts_provider: string
  voice: string
  bgm_enabled: boolean
  bgm_volume_db?: number
  video_aspect?: string
  video_concat_mode?: string
  clip_duration?: number
  transition?: string
  subtitle_position?: string
  subtitle_font_size?: number
  subtitle_color?: string
  subtitle_stroke_color?: string
  subtitle_stroke_width?: number
  publish_platforms?: string[]
  publish_title?: string
  prompt_audio?: string
  prompt_text?: string
  script_count?: number
  rewrite_style?: string
}
