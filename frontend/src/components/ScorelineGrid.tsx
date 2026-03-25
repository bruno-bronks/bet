import type { Scoreline } from '../types/prediction'

interface Props {
  scorelines: Scoreline[]
  homeTeam: string
  awayTeam: string
}

export default function ScorelineGrid({ scorelines, homeTeam, awayTeam }: Props) {
  if (!scorelines.length) return null

  const maxProb = Math.max(...scorelines.map((s) => s.probability))
  const top5 = scorelines.slice(0, 8)

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
        Placares Mais Prováveis
      </h3>

      <div className="grid grid-cols-4 gap-2">
        {top5.map((s, i) => {
          const intensity = s.probability / maxProb
          const isTopResult = i === 0
          return (
            <div
              key={s.scoreline}
              className={`relative rounded-xl p-3 text-center ring-1 transition-all ${
                isTopResult
                  ? 'bg-blue-50 ring-blue-300 shadow-sm'
                  : 'bg-gray-50 ring-gray-200'
              }`}
              style={{ opacity: 0.4 + intensity * 0.6 }}
            >
              {isTopResult && (
                <div className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-2 py-0.5 text-[9px] font-bold text-white uppercase tracking-wide">
                  TOP
                </div>
              )}
              <p className={`text-2xl font-black font-mono ${isTopResult ? 'text-blue-700' : 'text-gray-700'}`}>
                {s.scoreline}
              </p>
              <p className={`text-xs font-medium mt-1 font-mono ${isTopResult ? 'text-blue-500' : 'text-gray-400'}`}>
                {(s.probability * 100).toFixed(1)}%
              </p>
            </div>
          )
        })}
      </div>

      {/* Mini legend */}
      <div className="flex items-center gap-3 text-xs text-gray-400 pt-1 border-t border-gray-100">
        <span>{homeTeam} é o mandante</span>
        <span>·</span>
        <span>Baseado em modelo de Poisson bivariado</span>
      </div>
    </div>
  )
}
