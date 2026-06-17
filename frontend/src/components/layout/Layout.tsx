import { Outlet, NavLink } from 'react-router-dom'
import { Plus, ListVideo, Film, Settings, Zap, Wand2 } from 'lucide-react'
import clsx from 'clsx'

export function Layout() {
  return (
    <div className="flex h-full bg-surface-900">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}

function Sidebar() {
  const navItems = [
    { to: '/', icon: Wand2, label: '一键洗稿', end: true },
    { to: '/new', icon: Plus, label: '新建任务', end: false },
    { to: '/jobs', icon: ListVideo, label: '任务列表', end: false },
    { to: '/media', icon: Film, label: '素材库', end: false },
    { to: '/settings', icon: Settings, label: '设置', end: false },
  ]

  return (
    <aside className="w-56 shrink-0 flex flex-col bg-surface-800 border-r border-surface-600">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-surface-600">
        <div className="w-7 h-7 bg-brand-500 rounded-lg flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <span className="font-semibold text-white tracking-wide">Eidon</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                isActive
                  ? 'bg-brand-500/20 text-brand-400 font-medium'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-surface-600'
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-surface-600">
        <p className="text-xs text-zinc-600">AI Video Studio v1.0.0</p>
      </div>
    </aside>
  )
}
