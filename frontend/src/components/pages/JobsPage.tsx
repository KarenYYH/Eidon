import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, CheckCircle, XCircle, Loader2, AlertTriangle, Play } from 'lucide-react'
import clsx from 'clsx'
import { useJobStore } from '../../stores/jobStore'
import type { Job, JobStatus } from '../../types'

export function JobsPage() {
  const { jobs, loading, fetchJobs, watchJob } = useJobStore()
  const navigate = useNavigate()

  useEffect(() => {
    fetchJobs().then(() => {
      // Watch any running jobs
      jobs.filter(j => j.status === 'running' || j.status === 'pending').forEach(j => watchJob(j.id))
    })
  }, [])

  return (
    <div className="px-6 py-10 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white">任务列表</h1>
          <p className="text-sm text-zinc-400 mt-1">{jobs.length} 个任务</p>
        </div>
        <button onClick={() => navigate('/')} className="btn-primary flex items-center gap-2">
          <Play className="w-4 h-4" />
          新建任务
        </button>
      </div>

      {loading && jobs.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-zinc-500">暂无任务</p>
          <button onClick={() => navigate('/')} className="btn-primary mt-4">新建第一个任务</button>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map(job => (
            <JobRow key={job.id} job={job} onClick={() => navigate(`/jobs/${job.id}`)} />
          ))}
        </div>
      )}
    </div>
  )
}

function JobRow({ job, onClick }: { job: Job; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full card px-4 py-3 flex items-center gap-4 hover:border-surface-500 transition-all text-left">
      <StatusIcon status={job.status} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-200 truncate">{job.source_url || job.source_file || job.id}</p>
        <p className="text-xs text-zinc-500 mt-0.5">{new Date(job.created_at).toLocaleString('zh-CN')}</p>
      </div>
      <div className="shrink-0 flex items-center gap-3">
        {(job.status === 'running' || job.status === 'pending') && (
          <div className="w-24">
            <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            <p className="text-xs text-zinc-500 mt-0.5 text-right">{Math.round(job.progress)}%</p>
          </div>
        )}
        <StatusBadge status={job.status} />
      </div>
    </button>
  )
}

function StatusIcon({ status }: { status: JobStatus }) {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4 text-accent-400 shrink-0" />
    case 'failed': return <XCircle className="w-4 h-4 text-red-400 shrink-0" />
    case 'running': return <Loader2 className="w-4 h-4 text-brand-400 shrink-0 animate-spin" />
    case 'cancelled': return <AlertTriangle className="w-4 h-4 text-zinc-500 shrink-0" />
    default: return <Clock className="w-4 h-4 text-zinc-500 shrink-0" />
  }
}

function StatusBadge({ status }: { status: JobStatus }) {
  const map: Record<JobStatus, { label: string; cls: string }> = {
    pending: { label: '等待中', cls: 'bg-zinc-700 text-zinc-300' },
    running: { label: '处理中', cls: 'bg-brand-500/20 text-brand-400' },
    completed: { label: '完成', cls: 'bg-accent-500/20 text-accent-400' },
    failed: { label: '失败', cls: 'bg-red-500/20 text-red-400' },
    cancelled: { label: '已取消', cls: 'bg-zinc-700 text-zinc-500' },
  }
  const { label, cls } = map[status]
  return <span className={clsx('badge', cls)}>{label}</span>
}
