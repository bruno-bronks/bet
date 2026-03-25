import { useEffect, useState } from 'react'
import { Cpu, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import type { ModelItem } from '../types/prediction'
import { clsx } from 'clsx'

const MODEL_LABELS: Record<string, string> = {
  outcome: 'Resultado 1X2',
  goals: 'Gols (Poisson)',
  corners: 'Escanteios',
  cards: 'Cartões',
  time_window: 'Janelas Temporais',
}

const MODEL_ICONS: Record<string, string> = {
  outcome: '🏆',
  goals: '⚽',
  corners: '📐',
  cards: '🟨',
  time_window: '⏱',
}

const COMP_LABELS: Record<string, { label: string; flag: string; color: string }> = {
  brasileirao: { label: 'Brasileirão', flag: '🇧🇷', color: 'text-green-600' },
  champions_league: { label: 'Champions League', flag: '🌍', color: 'text-blue-600' },
  all: { label: 'Todas', flag: '🌐', color: 'text-gray-500' },
}

interface TrainState {
  loading: boolean
  success: boolean | null
  message: string
}

export default function Models() {
  const [models, setModels] = useState<ModelItem[]>([])
  const [loading, setLoading] = useState(true)
  const [trainState, setTrainState] = useState<Record<string, TrainState>>({})

  const fetchModels = () => {
    setLoading(true)
    api.listModels()
      .then((r) => setModels(r.models))
      .catch(() => setModels([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchModels() }, [])

  const handleTrain = async (competition: string) => {
    setTrainState((prev) => ({
      ...prev,
      [competition]: { loading: true, success: null, message: 'Treinando...' },
    }))
    try {
      const r = await api.train({ competition, force_retrain: true })
      setTrainState((prev) => ({
        ...prev,
        [competition]: { loading: false, success: true, message: r.message || 'Concluído' },
      }))
      fetchModels()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro no treinamento'
      setTrainState((prev) => ({
        ...prev,
        [competition]: { loading: false, success: false, message: msg },
      }))
    }
  }

  const byComp = models.reduce<Record<string, ModelItem[]>>((acc, m) => {
    const k = m.competition || 'all'
    acc[k] = [...(acc[k] || []), m]
    return acc
  }, {})

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-16">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Cpu size={22} className="text-blue-600" />
              Modelos Registrados
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {models.length} modelo(s) disponível(eis) em disco
            </p>
          </div>
          <button
            onClick={fetchModels}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 px-3 py-2 text-sm text-gray-600 transition-all shadow-sm"
          >
            <RefreshCw size={14} />
            Atualizar
          </button>
        </div>

        {/* Train buttons */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {['brasileirao', 'champions_league'].map((comp) => {
            const state = trainState[comp]
            const info = COMP_LABELS[comp]
            return (
              <div key={comp} className="rounded-xl border border-gray-200 bg-white p-5 space-y-3 shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{info.flag}</span>
                  <p className={`font-semibold ${info.color}`}>{info.label}</p>
                </div>

                {state && !state.loading && (
                  <div className={`flex items-start gap-2 text-xs ${
                    state.success ? 'text-emerald-600' : 'text-rose-500'
                  }`}>
                    {state.success
                      ? <CheckCircle size={13} className="shrink-0 mt-0.5" />
                      : <XCircle size={13} className="shrink-0 mt-0.5" />
                    }
                    {state.message}
                  </div>
                )}

                <button
                  onClick={() => handleTrain(comp)}
                  disabled={state?.loading}
                  className={clsx(
                    'w-full rounded-lg py-2 text-xs font-semibold transition-all',
                    state?.loading
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
                      : 'bg-gray-800 hover:bg-gray-900 text-white'
                  )}
                >
                  {state?.loading ? (
                    <span className="flex items-center justify-center gap-1.5">
                      <span className="h-3 w-3 animate-spin rounded-full border border-gray-400 border-t-white" />
                      Treinando...
                    </span>
                  ) : 'Treinar Todos os Modelos'}
                </button>
              </div>
            )
          })}
        </div>

        {/* Models list */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 rounded-xl bg-gray-200 animate-pulse" />
            ))}
          </div>
        ) : models.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 py-20 text-center bg-white">
            <AlertCircle size={32} className="text-gray-300 mb-4" />
            <p className="text-gray-500 font-medium">Nenhum modelo encontrado</p>
            <p className="text-gray-400 text-sm mt-1">
              Execute os scripts de treinamento ou use o botão acima
            </p>
            <code className="mt-4 text-xs text-gray-500 bg-gray-100 px-3 py-2 rounded-lg font-mono border border-gray-200">
              python scripts/train_all.py
            </code>
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(byComp).map(([comp, items]) => {
              const info = COMP_LABELS[comp] || COMP_LABELS.all
              return (
                <div key={comp}>
                  <div className="flex items-center gap-2 mb-3">
                    <span>{info.flag}</span>
                    <h2 className={`text-sm font-bold uppercase tracking-wide ${info.color}`}>
                      {info.label}
                    </h2>
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-xs text-gray-400">{items.length} modelos</span>
                  </div>

                  <div className="space-y-2">
                    {items.map((m) => {
                      const label = MODEL_LABELS[m.model_type] || m.model_type
                      const icon = MODEL_ICONS[m.model_type] || '📊'
                      const metricKeys = Object.keys(m.metrics)
                      return (
                        <div
                          key={m.key}
                          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 hover:border-gray-300 hover:shadow-sm transition-all"
                        >
                          <span className="text-xl">{icon}</span>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm text-gray-800">{label}</p>
                            <p className="text-xs text-gray-400 font-mono truncate">
                              {m.path ? m.path.split(/[/\\]/).slice(-2).join('/') : m.key}
                            </p>
                          </div>

                          {/* Metrics */}
                          {metricKeys.length > 0 && (
                            <div className="flex flex-wrap gap-2 justify-end">
                              {metricKeys.slice(0, 3).map((k) => (
                                <div key={k} className="rounded-md bg-gray-50 border border-gray-200 px-2 py-1 text-center">
                                  <p className="text-[10px] text-gray-400 uppercase">{k.replace(/_/g, ' ')}</p>
                                  <p className="text-xs font-mono font-bold text-gray-700">
                                    {typeof m.metrics[k] === 'number'
                                      ? (m.metrics[k] as number).toFixed(3)
                                      : String(m.metrics[k])}
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}

                          <div className="rounded-md bg-emerald-50 ring-1 ring-emerald-200 px-2 py-1">
                            <p className="text-xs text-emerald-600 font-medium">Ativo</p>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
