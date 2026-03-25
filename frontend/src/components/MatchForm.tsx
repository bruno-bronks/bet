import { useState, FormEvent } from 'react'
import { Search, Trophy, Calendar } from 'lucide-react'
import { clsx } from 'clsx'
import type { PredictRequest } from '../types/prediction'

interface Props {
  onSubmit: (req: PredictRequest) => void
  loading: boolean
}

const BRASILEIRAO_TEAMS = [
  'Flamengo', 'Palmeiras', 'Atletico Mineiro', 'Corinthians', 'Fluminense',
  'Botafogo', 'Cruzeiro', 'Gremio', 'Internacional', 'Sao Paulo',
  'Santos', 'Vasco', 'Bahia', 'Fortaleza', 'Atletico Goianiense',
  'Bragantino', 'Coritiba', 'America Mineiro', 'Cuiaba', 'Goias',
]

const UCL_TEAMS = [
  'Real Madrid', 'Manchester City', 'Bayern Munich', 'Psg', 'Liverpool',
  'Chelsea', 'Barcelona', 'Juventus', 'Borussia Dortmund', 'Inter Milan',
  'Atletico Madrid', 'Ajax', 'Porto', 'Benfica', 'Napoli', 'Ac Milan',
  'Arsenal', 'Tottenham', 'Lyon', 'Sevilla', 'Rb Leipzig', 'Sporting Cp',
]

const UCL_STAGES = [
  { value: 'group', label: 'Fase de Grupos' },
  { value: 'round_of_16', label: 'Oitavas de Final' },
  { value: 'quarter_final', label: 'Quartas de Final' },
  { value: 'semi_final', label: 'Semifinal' },
  { value: 'final', label: 'Final' },
]

export default function MatchForm({ onSubmit, loading }: Props) {
  const [competition, setCompetition] = useState<'brasileirao' | 'champions_league'>('brasileirao')
  const [homeTeam, setHomeTeam] = useState('')
  const [awayTeam, setAwayTeam] = useState('')
  const [matchDate, setMatchDate] = useState(new Date().toISOString().split('T')[0])
  const [stage, setStage] = useState('')
  const [matchday, setMatchday] = useState('')
  const [explanation, setExplanation] = useState(false)

  const teams = competition === 'brasileirao' ? BRASILEIRAO_TEAMS : UCL_TEAMS
  const isUCL = competition === 'champions_league'

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!homeTeam || !awayTeam || !matchDate) return
    onSubmit({
      competition,
      home_team: homeTeam,
      away_team: awayTeam,
      match_date: matchDate,
      stage: stage || undefined,
      matchday: matchday ? parseInt(matchday) : undefined,
      include_explanation: explanation,
    })
  }

  const inputClass = "w-full rounded-lg bg-white border border-gray-200 px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-200 transition-colors"
  const labelClass = "block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide"

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-gray-200 bg-white p-6 space-y-5 shadow-sm">
      <h2 className="text-base font-bold text-gray-800 flex items-center gap-2">
        <Search size={16} className="text-blue-600" />
        Configurar Análise
      </h2>

      {/* Competition selector */}
      <div>
        <label className={labelClass}>Competição</label>
        <div className="grid grid-cols-2 gap-2">
          {[
            { value: 'brasileirao', label: '🇧🇷 Brasileirão', sub: 'Série A' },
            { value: 'champions_league', label: '🌍 Champions', sub: 'UEFA' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { setCompetition(opt.value as typeof competition); setHomeTeam(''); setAwayTeam(''); setStage('') }}
              className={clsx(
                'rounded-lg border p-3 text-left transition-all',
                competition === opt.value
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-gray-200 bg-gray-50 text-gray-500 hover:border-gray-300 hover:bg-white'
              )}
            >
              <p className="text-sm font-semibold">{opt.label}</p>
              <p className="text-xs opacity-60 mt-0.5">{opt.sub}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Teams */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Mandante</label>
          <select
            value={homeTeam}
            onChange={(e) => setHomeTeam(e.target.value)}
            required
            className={inputClass}
          >
            <option value="">Selecione...</option>
            {teams.map((t) => (
              <option key={t} value={t} disabled={t === awayTeam}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Visitante</label>
          <select
            value={awayTeam}
            onChange={(e) => setAwayTeam(e.target.value)}
            required
            className={inputClass}
          >
            <option value="">Selecione...</option>
            {teams.map((t) => (
              <option key={t} value={t} disabled={t === homeTeam}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Date */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>
            <Calendar size={11} className="inline mr-1" />
            Data da Partida
          </label>
          <input
            type="date"
            value={matchDate}
            onChange={(e) => setMatchDate(e.target.value)}
            required
            className={inputClass}
          />
        </div>

        {isUCL ? (
          <div>
            <label className={labelClass}>Fase</label>
            <select value={stage} onChange={(e) => setStage(e.target.value)} className={inputClass}>
              <option value="">Selecione...</option>
              {UCL_STAGES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <label className={labelClass}>Rodada</label>
            <input
              type="number"
              min={1}
              max={38}
              value={matchday}
              onChange={(e) => setMatchday(e.target.value)}
              placeholder="1–38"
              className={inputClass}
            />
          </div>
        )}
      </div>

      {/* Options */}
      <label className="flex items-center gap-2.5 cursor-pointer group">
        <div className={clsx(
          'h-4 w-4 rounded border flex items-center justify-center transition-all shrink-0',
          explanation ? 'border-blue-500 bg-blue-500' : 'border-gray-300 bg-transparent group-hover:border-gray-400'
        )}>
          {explanation && <span className="text-[10px] text-white font-bold">✓</span>}
        </div>
        <input type="checkbox" checked={explanation} onChange={(e) => setExplanation(e.target.checked)} className="sr-only" />
        <span className="text-sm text-gray-500 group-hover:text-gray-700 transition-colors">
          Incluir explicação em linguagem natural
        </span>
      </label>

      {/* Submit */}
      <button
        type="submit"
        disabled={loading || !homeTeam || !awayTeam}
        className={clsx(
          'w-full rounded-lg py-3 text-sm font-semibold transition-all',
          loading || !homeTeam || !awayTeam
            ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
            : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg'
        )}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Analisando...
          </span>
        ) : 'Analisar Partida'}
      </button>
    </form>
  )
}
