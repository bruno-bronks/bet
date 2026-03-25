import { Link, useLocation } from 'react-router-dom'
import { Activity, BarChart3, Calendar, Cpu, History } from 'lucide-react'
import { clsx } from 'clsx'

const LINKS = [
  { to: '/', label: 'Partidas', icon: Calendar, exact: true },
  { to: '/predict', label: 'Análise Manual', icon: Activity, exact: false },
  { to: '/historico', label: 'Histórico', icon: History, exact: false },
  { to: '/models', label: 'Modelos', icon: Cpu, exact: false },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur-md shadow-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 shadow-sm">
              <BarChart3 className="h-4.5 w-4.5 text-white" size={18} />
            </div>
            <span className="font-bold tracking-tight text-gray-900">
              Football <span className="text-blue-600">Analytics</span>
            </span>
          </Link>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            {LINKS.map(({ to, label, icon: Icon, exact }) => {
              const isActive = exact ? pathname === to : pathname.startsWith(to)
              return (
                <Link
                  key={to}
                  to={to}
                  className={clsx(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all',
                    isActive
                      ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200'
                      : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'
                  )}
                >
                  <Icon size={15} />
                  {label}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>
    </header>
  )
}
