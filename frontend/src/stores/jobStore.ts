import { create } from 'zustand'
import type { Job } from '../types'
import { listJobs, createJob, cancelJob, createJobWebSocket, uploadAndCreateJob } from '../utils/api'
import type { CreateJobPayload } from '../types'

interface JobStore {
  jobs: Job[]
  activeJobId: string | null
  loading: boolean
  wsConnections: Map<string, WebSocket>

  fetchJobs: () => Promise<void>
  submitJob: (payload: CreateJobPayload) => Promise<Job>
  submitUpload: (file: File, payload: { target_language: string; tts_provider: string; voice: string; bgm_enabled: boolean }) => Promise<Job>
  cancelJob: (id: string) => Promise<void>
  setActiveJob: (id: string | null) => void
  updateJob: (job: Job) => void
  watchJob: (id: string) => void
}

export const useJobStore = create<JobStore>((set, get) => ({
  jobs: [],
  activeJobId: null,
  loading: false,
  wsConnections: new Map(),

  fetchJobs: async () => {
    set({ loading: true })
    try {
      const jobs = await listJobs()
      set({ jobs, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  submitJob: async (payload) => {
    const job = await createJob(payload)
    set(s => ({ jobs: [job, ...s.jobs], activeJobId: job.id }))
    get().watchJob(job.id)
    return job
  },

  submitUpload: async (file, payload) => {
    const job = await uploadAndCreateJob(file, payload)
    set(s => ({ jobs: [job, ...s.jobs], activeJobId: job.id }))
    get().watchJob(job.id)
    return job
  },

  cancelJob: async (id) => {
    await cancelJob(id)
    get().fetchJobs()
  },

  setActiveJob: (id) => set({ activeJobId: id }),

  updateJob: (job) => set(s => ({
    jobs: s.jobs.map(j => j.id === job.id ? job : j),
  })),

  watchJob: (id) => {
    const { wsConnections, updateJob } = get()
    if (wsConnections.has(id)) return
    const ws = createJobWebSocket(id, (job) => updateJob(job))
    ws.onclose = () => {
      const conns = get().wsConnections
      conns.delete(id)
      set({ wsConnections: new Map(conns) })
    }
    wsConnections.set(id, ws)
    set({ wsConnections: new Map(wsConnections) })
  },
}))
