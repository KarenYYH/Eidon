import { useState, useEffect } from 'react'
import { Settings, CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react'
import { getLLMConfig, saveLLMConfig, testLLM } from '../../utils/api'

export function SettingsPage() {
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('gpt-4o-mini')
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    getLLMConfig().then(cfg => {
      setBaseUrl(cfg.base_url || '')
      setModel(cfg.model || 'gpt-4o-mini')
      // key stays blank — user must re-enter to change
    }).catch(() => {})
  }, [])

  async function handleSave() {
    setSaving(true); setSaveMsg(null)
    try {
      await saveLLMConfig({ api_key: apiKey, base_url: baseUrl, model })
      setSaveMsg({ ok: true, text: '保存成功' })
    } catch {
      setSaveMsg({ ok: false, text: '保存失败，请检查后端是否运行' })
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    if (!apiKey) { setTestMsg({ ok: false, text: '请先填写 API Key' }); return }
    setTesting(true); setTestMsg(null)
    try {
      const res = await testLLM({ api_key: apiKey, base_url: baseUrl, model })
      if (res.status === 'ok') {
        setTestMsg({ ok: true, text: `连接成功：${res.reply}` })
      } else {
        setTestMsg({ ok: false, text: res.message || '连接失败' })
      }
    } catch {
      setTestMsg({ ok: false, text: '请求失败，请检查后端是否运行' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-brand-400" />
          设置
        </h1>
        <p className="text-sm text-zinc-400 mt-1">配置 LLM 接口，支持 OpenAI 格式的中转站</p>
      </div>

      <div className="card p-6 space-y-5">
        <h2 className="text-sm font-medium text-zinc-200">LLM 配置（翻译 & 脚本生成）</h2>

        <div>
          <label className="text-xs text-zinc-400 mb-1.5 block">API Key</label>
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              className="input pr-10"
              placeholder="sk-..."
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setShowKey(v => !v)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
            >
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div>
          <label className="text-xs text-zinc-400 mb-1.5 block">
            Base URL <span className="text-zinc-600">（留空 = 官方 OpenAI；填写支持中转站）</span>
          </label>
          <input
            type="text"
            className="input"
            placeholder="https://api.openai.com/v1"
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
          />
        </div>

        <div>
          <label className="text-xs text-zinc-400 mb-1.5 block">模型名称</label>
          <input
            type="text"
            className="input"
            placeholder="gpt-4o-mini"
            value={model}
            onChange={e => setModel(e.target.value)}
          />
          <p className="text-xs text-zinc-600 mt-1">常用：gpt-4o-mini · gpt-4o · deepseek-chat · qwen-turbo</p>
        </div>

        {saveMsg && (
          <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${saveMsg.ok ? 'bg-accent-500/10 text-accent-400' : 'bg-red-500/10 text-red-400'}`}>
            {saveMsg.ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {saveMsg.text}
          </div>
        )}

        {testMsg && (
          <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${testMsg.ok ? 'bg-accent-500/10 text-accent-400' : 'bg-red-500/10 text-red-400'}`}>
            {testMsg.ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {testMsg.text}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button
            onClick={handleTest}
            disabled={testing}
            className="btn-ghost border border-surface-500 flex items-center gap-2 text-sm"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            测试连接
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !apiKey}
            className="btn-primary flex items-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            保存配置
          </button>
        </div>
      </div>
    </div>
  )
}
