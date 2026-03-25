import { Link } from 'react-router-dom'
import { Activity, BarChart3, Brain, CheckCircle, Shield, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

const FEATURES = [
  {
    icon: Brain,
    title: 'Modelos Probabilísticos',
    desc: 'LightGBM calibrado, Poisson para gols, classificação binária para eventos temporais.',
    color: 'text-brand-400',
    bg: 'bg-brand-500/10',
  },
  {
    icon: BarChart3,
    title: 'Múltiplos Mercados',
    desc: 'Resultado 1X2, gols, escanteios, cartões, ambas marcam, placares e janelas temporais.',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
  },
  {
    icon: Zap,
    title: 'ELO Rating Dinâmico',
    desc: 'Rating atualizado partida a partida sem data leakage. Captura força relativa em tempo real.',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
  },
  {
    icon: Shield,
    title: 'Calibração Rigorosa',
    desc: 'Brier Score, ECE e Log-Loss monitorados. Probabilidades refletem frequências reais.',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
  },
]

const COMPETITIONS = [
  {
    flag: '🇧🇷',
    name: 'Brasileirão',
    sub: 'Série A — 38 rodadas',
    id: 'brasileirao',
    color: 'from-green-500/20 to-yellow-500/20',
    ring: 'ring-green-500/20',
  },
  {
    flag: '🌍',
    name: 'Champions League',
    sub: 'UEFA — Grupos + Mata-mata',
    id: 'champions_league',
    color: 'from-brand-500/20 to-purple-500/20',
    ring: 'ring-brand-500/20',
  },
]

const EVENTS = [
  'Vitória / Empate / Derrota', 'Expected Goals (xG)',
  'Over/Under 0.5 → 4.5', 'Ambas as equipes marcam',
  'Placares mais prováveis', 'Gol nos primeiros 15\'',
  'Gol nos últimos 15\'', 'Escanteios totais por equipe',
  'Cartões por equipe', 'Pressão ofensiva por tempo',
]

export default function Home() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'error'>('checking')

  useEffect(() => {
    api.health()
      .then(() => setApiStatus('ok'))
      .catch(() => setApiStatus('error'))
  }, [])

  return (
    <div className="min-h-screen pt-16">

      {/* Hero */}
      <section className="relative overflow-hidden py-24 px-4">
        {/* Background glow */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full bg-brand-500/10 blur-3xl" />
        </div>

        <div className="mx-auto max-w-4xl text-center space-y-6">
          {/* API status badge */}
          <div className="flex justify-center">
            <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ring-1 ${
              apiStatus === 'ok'
                ? 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/25'
                : apiStatus === 'error'
                ? 'bg-rose-500/10 text-rose-400 ring-rose-500/25'
                : 'bg-slate-800 text-slate-500 ring-white/10'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                apiStatus === 'ok' ? 'bg-emerald-400 animate-pulse' :
                apiStatus === 'error' ? 'bg-rose-400' : 'bg-slate-500'
              }`} />
              {apiStatus === 'ok' ? 'API Online' : apiStatus === 'error' ? 'API Offline' : 'Verificando API...'}
            </div>
          </div>

          <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-white leading-tight">
            Análise Probabilística{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 to-purple-400">
              de Futebol
            </span>
          </h1>

          <p className="text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Plataforma estatística para{' '}
            <span className="text-white font-medium">Brasileirão</span> e{' '}
            <span className="text-white font-medium">UEFA Champions League</span>.
            Estimativas probabilísticas para múltiplos eventos por partida.
          </p>

          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-sm text-amber-400/80 max-w-lg mx-auto">
            ⚠ As probabilidades são estimativas baseadas em dados históricos.
            Não constituem garantia de resultado.
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link
              to="/predict"
              className="rounded-xl bg-brand-500 hover:bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40 transition-all"
            >
              Iniciar Análise →
            </Link>
            <Link
              to="/models"
              className="rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 px-6 py-3 text-sm font-semibold text-slate-300 transition-all"
            >
              Ver Modelos
            </Link>
          </div>
        </div>
      </section>

      {/* Competitions */}
      <section className="py-16 px-4 border-t border-white/5">
        <div className="mx-auto max-w-4xl">
          <p className="text-center text-xs font-semibold uppercase tracking-widest text-slate-600 mb-8">
            Competições Suportadas
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {COMPETITIONS.map((c) => (
              <Link
                key={c.id}
                to="/predict"
                className={`group rounded-2xl bg-gradient-to-br ${c.color} ring-1 ${c.ring} p-6 hover:ring-2 transition-all`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-3xl">{c.flag}</span>
                  <div>
                    <p className="font-bold text-white">{c.name}</p>
                    <p className="text-xs text-slate-500">{c.sub}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">
                  Clique para analisar →
                </p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Eventos estimados */}
      <section className="py-16 px-4 border-t border-white/5">
        <div className="mx-auto max-w-4xl">
          <p className="text-center text-xs font-semibold uppercase tracking-widest text-slate-600 mb-8">
            Eventos Estimados por Partida
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {EVENTS.map((e) => (
              <span
                key={e}
                className="rounded-lg bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-400 ring-1 ring-white/6"
              >
                {e}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 px-4 border-t border-white/5">
        <div className="mx-auto max-w-5xl">
          <p className="text-center text-xs font-semibold uppercase tracking-widest text-slate-600 mb-10">
            Tecnologia
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-white/6 bg-pitch-800/30 p-5 flex gap-4">
                <div className={`${f.bg} rounded-lg p-2.5 h-fit ring-1 ring-white/5`}>
                  <f.icon size={18} className={f.color} />
                </div>
                <div>
                  <p className="font-semibold text-slate-200 text-sm">{f.title}</p>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 px-4 text-center">
        <p className="text-xs text-slate-700">
          Football Analytics Platform · Análise probabilística estatística ·{' '}
          Dados sintéticos para demonstração
        </p>
      </footer>

    </div>
  )
}
