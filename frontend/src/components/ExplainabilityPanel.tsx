import { AlertTriangle, CheckCircle, Info } from 'lucide-react'
import type { ExplainabilityInfo, FeatureImportance } from '../types/prediction'

interface Props {
  explain: ExplainabilityInfo
  explanation?: string
  warnings: string[]
}

function FeatureBar({ feat, max }: { feat: FeatureImportance; max: number }) {
  const val = feat.shap_importance ?? feat.importance ?? 0
  const width = max > 0 ? (val / max) * 100 : 0
  const label = feat.feature
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div className="flex items-center gap-3">
      <span className="w-44 text-xs text-gray-500 truncate shrink-0">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-400"
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="w-14 text-right text-xs font-mono text-gray-400">
        {val.toFixed(4)}
      </span>
    </div>
  )
}

export default function ExplainabilityPanel({ explain, explanation, warnings }: Props) {
  const maxVal = explain.top_features.length > 0
    ? Math.max(...explain.top_features.map((f) => f.shap_importance ?? f.importance ?? 0))
    : 1

  const confidencePct = Math.round(explain.confidence_score * 100)

  return (
    <div className="space-y-4">

      {/* Confidence */}
      <div className={`rounded-xl p-4 ring-1 flex items-center gap-4 ${
        explain.low_confidence_warning
          ? 'bg-amber-50 ring-amber-200'
          : 'bg-emerald-50 ring-emerald-200'
      }`}>
        {explain.low_confidence_warning
          ? <AlertTriangle className="text-amber-500 shrink-0" size={20} />
          : <CheckCircle className="text-emerald-600 shrink-0" size={20} />
        }
        <div className="flex-1">
          <p className={`text-sm font-semibold ${explain.low_confidence_warning ? 'text-amber-700' : 'text-emerald-700'}`}>
            Confiança do Modelo: {confidencePct}%
          </p>
          {explain.low_confidence_warning && (
            <p className="text-xs text-amber-600 mt-0.5">
              Histórico insuficiente — estimativas menos confiáveis
            </p>
          )}
        </div>
        <div className={`text-2xl font-black font-mono ${
          explain.low_confidence_warning ? 'text-amber-600' : 'text-emerald-600'
        }`}>
          {confidencePct}%
        </div>
      </div>

      {/* Feature importance */}
      {explain.top_features.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Info size={14} className="text-gray-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
              Fatores mais relevantes
            </h3>
            <span className="ml-auto text-xs text-gray-400 font-mono">
              {explain.top_features[0]?.method === 'shap' ? 'SHAP' : 'Feature Importance'}
            </span>
          </div>
          <div className="space-y-2">
            {explain.top_features.slice(0, 8).map((f, i) => (
              <FeatureBar key={`${f.feature}-${i}`} feat={f} max={maxVal} />
            ))}
          </div>
        </div>
      )}

      {/* Natural language explanation */}
      {explanation && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
            Resumo da Análise
          </p>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
            {explanation}
          </p>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-1">
          <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">Alertas</p>
          {warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-600 flex items-start gap-2">
              <span className="mt-0.5 shrink-0">⚠</span>
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
