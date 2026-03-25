import { Clock } from 'lucide-react'
import type { TimeWindowsInfo } from '../types/prediction'

interface Props {
  timeWindows: TimeWindowsInfo
}

interface WindowCardProps {
  label: string
  sublabel: string
  value: number
  minutes: string
}

function WindowCard({ label, sublabel, value, minutes }: WindowCardProps) {
  const pct = (value * 100).toFixed(0)
  const high = value >= 0.65

  return (
    <div className={`rounded-xl p-4 ring-1 transition-all space-y-3 ${
      high ? 'bg-blue-50 ring-blue-200' : 'bg-gray-50 ring-gray-200'
    }`}>
      <div className="flex items-start justify-between">
        <div>
          <p className={`text-sm font-semibold ${high ? 'text-blue-800' : 'text-gray-700'}`}>{label}</p>
          <p className="text-xs text-gray-500 mt-0.5">{sublabel}</p>
        </div>
        <div className="flex items-center gap-1 rounded-md bg-white border border-gray-200 px-2 py-1">
          <Clock size={11} className="text-gray-400" />
          <span className="text-xs text-gray-500 font-mono">{minutes}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="h-2 w-full rounded-full bg-gray-200 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              high ? 'bg-blue-500' : 'bg-gray-400'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className={`text-right text-xl font-black font-mono ${high ? 'text-blue-600' : 'text-gray-600'}`}>
          {pct}%
        </p>
      </div>
    </div>
  )
}

export default function TimeWindowCards({ timeWindows }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
        Probabilidade por Janela Temporal
      </h3>

      <div className="grid grid-cols-2 gap-3">
        <WindowCard
          label="Gol nos primeiros 15'"
          sublabel="Início de jogo"
          value={timeWindows.goal_first_15min}
          minutes="0–15"
        />
        <WindowCard
          label="Gol no 1º Tempo"
          sublabel="Antes do intervalo"
          value={timeWindows.goal_first_half}
          minutes="0–45"
        />
        <WindowCard
          label="Gol no 2º Tempo"
          sublabel="Após o intervalo"
          value={timeWindows.goal_second_half}
          minutes="45–90"
        />
        <WindowCard
          label="Gol nos últimos 15'"
          sublabel="Final de jogo"
          value={timeWindows.goal_last_15min}
          minutes="75–90"
        />
      </div>
    </div>
  )
}
