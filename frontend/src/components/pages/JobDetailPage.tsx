import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, X, CheckCircle, XCircle, Loader2, Clock, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useJobStore } from '../../stores/jobStore'
import { listJobChildren } from '../../utils/api'
import type { Job, StepStatus, JobStatus } from '../../types'

const STEP_LABELS: Record<string, string> = {
  download: '下载视频',
  transcribe: '语音识别',
  translate: '翻译字幕',
  tts: 'TTS 配音',
  script: '生成脚本',
  rewrite: 'AI 改写口播稿',
  assemble: '拼接场景',
  synthesize: '合成视频',
  lipsync: '数字人合成',
  dispatch: '派发子任务',
  publish: '发布',
}

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { jobs, watchJob, cancelJob } = useJobStore()
  const job = jobs.find(j => j.id === id)
  const [children, setChildren] = useState<Job[]>([])

  useEffect(() => {
    if (id) watchJob(id)
  }, [id])

  // Poll children while a rewrite parent is dispatching/running
  useEffect(() => {
    if (!id || job?.mode !== 'rewrite') return
    const load = () => listJobChildren(id).then(setChildren).catch(() => {})
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [id, job?.mode, job?.status])

  if (!job) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-zinc-500">任务不存在</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <button onClick={() => navigate('/jobs')} className="btn-ghost flex items-center gap-1.5 mb-6 -ml-1">
        <ArrowLeft className="w-4 h-4" />
        返回列表
      </button>

      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-white break-all line-clamp-2">
            {job.source_url || job.source_file || job.id}
          </h1>
          <p className="text-xs text-zinc-500 mt-1">{new Date(job.created_at).toLocaleString('zh-CN')}</p>
        </div>
        {(job.status === 'running' || job.status === 'pending') && (
          <button onClick={() => cancelJob(job.id)} className="btn-ghost text-red-400 hover:text-red-300 flex items-center gap-1.5 shrink-0 ml-4">
            <X className="w-4 h-4" />
            取消
          </button>
        )}
      </div>

      {/* Overall progress */}
      <div className="card p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-zinc-300">总进度</span>
          <span className="text-sm font-medium text-zinc-200">{Math.round(job.progress)}%</span>
        </div>
        <div className="h-2 bg-surface-600 rounded-full overflow-hidden">
          <div
            className={clsx('h-full rounded-full transition-all duration-700',
              job.status === 'failed' ? 'bg-red-500' :
              job.status === 'completed' ? 'bg-accent-500' : 'bg-brand-500'
            )}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>

      {/* Steps */}
      <div className="card divide-y divide-surface-600 mb-6">
        {job.steps.map(step => (
          <StepRow key={step.step} step={step} />
        ))}
      </div>

      {/* Rewrite: generated scripts + spawned child jobs */}
      {job.mode === 'rewrite' && (job.scripts?.length || children.length > 0) && (
        <div className="card p-4 mb-6">
          <p className="text-sm text-zinc-300 font-medium mb-3">
            改写口播稿与数字人任务（{children.length || job.scripts?.length || 0}）
          </p>
          <div className="space-y-2">
            {(job.scripts || []).map((script, i) => {
              const child = children[i]
              return (
                <div key={i} className="bg-surface-700 rounded-lg p-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs text-brand-400 font-medium">第 {i + 1} 条</span>
                    {child && (
                      <button onClick={() => navigate(`/jobs/${child.id}`)}
                        className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1">
                        <StepIcon status={child.status} />
                        查看任务
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-zinc-300 line-clamp-3">{script}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Child job: back-link to parent */}
      {job.parent_id && (
        <button onClick={() => navigate(`/jobs/${job.parent_id}`)}
          className="btn-ghost text-sm flex items-center gap-1.5 mb-6">
          <ArrowLeft className="w-3.5 h-3.5" />
          返回批量改写任务
        </button>
      )}

      {/* Error */}
      {job.error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-300 font-medium mb-1">处理失败</p>
          <p className="text-xs text-red-400 font-mono break-all">{job.error}</p>
        </div>
      )}

      {/* Download */}
      {job.status === 'completed' && job.output_file && (
        <a
          href={`/api/jobs/${job.id}/download`}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 no-underline"
        >
          <Download className="w-4 h-4" />
          下载视频
        </a>
      )}
    </div>
  )
}

function StepRow({ step }: { step: StepStatus }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <StepIcon status={step.status} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-zinc-300">{STEP_LABELS[step.step] || step.step}</span>
          {step.status === 'running' && (
            <span className="text-xs text-brand-400">{Math.round(step.progress)}%</span>
          )}
        </div>
        {step.message && (
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{step.message}</p>
        )}
        {step.error && (
          <p className="text-xs text-red-400 mt-0.5 truncate">{step.error}</p>
        )}
        {step.status === 'running' && (
          <div className="h-1 bg-surface-600 rounded-full overflow-hidden mt-1.5">
            <div
              className="h-full bg-brand-500 rounded-full transition-all duration-500"
              style={{ width: `${step.progress}%` }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function StepIcon({ status }: { status: JobStatus }) {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4 text-accent-400 shrink-0" />
    case 'failed': return <XCircle className="w-4 h-4 text-red-400 shrink-0" />
    case 'running': return <Loader2 className="w-4 h-4 text-brand-400 shrink-0 animate-spin" />
    case 'cancelled': return <AlertTriangle className="w-4 h-4 text-zinc-500 shrink-0" />
    default: return <Clock className="w-4 h-4 text-zinc-600 shrink-0" />
  }
}
