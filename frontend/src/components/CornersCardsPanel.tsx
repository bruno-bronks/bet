import { Triangle, CreditCard } from 'lucide-react'
import type { CornersInfo, CardsInfo } from '../types/prediction'

interface Props {
  corners: CornersInfo
  cards: CardsInfo
  homeTeam: string
  awayTeam: string
}

export default function CornersCardsPanel({ corners, cards, homeTeam, awayTeam }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

      {/* Corners */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-orange-50 p-1.5 ring-1 ring-orange-200">
            <Triangle size={14} className="text-orange-500" />
          </div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">Escanteios</h3>
        </div>

        <div className="flex items-end justify-center gap-4 py-2">
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1 truncate">{homeTeam}</p>
            <p className="text-3xl font-black text-emerald-600 font-mono">
              {corners.expected_corners_home.toFixed(1)}
            </p>
          </div>
          <div className="text-center pb-1">
            <p className="text-lg font-bold text-gray-300">+</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1 truncate">{awayTeam}</p>
            <p className="text-3xl font-black text-rose-500 font-mono">
              {corners.expected_corners_away.toFixed(1)}
            </p>
          </div>
        </div>

        <div className="rounded-lg bg-orange-50 ring-1 ring-orange-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-0.5">Total esperado</p>
          <p className="text-2xl font-black text-orange-600 font-mono">
            {corners.expected_corners_total.toFixed(1)}
          </p>
        </div>
      </div>

      {/* Cards */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-yellow-50 p-1.5 ring-1 ring-yellow-200">
            <CreditCard size={14} className="text-yellow-500" />
          </div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500">Cartões</h3>
        </div>

        <div className="flex items-end justify-center gap-4 py-2">
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1 truncate">{homeTeam}</p>
            <p className="text-3xl font-black text-emerald-600 font-mono">
              {cards.expected_cards_home.toFixed(1)}
            </p>
          </div>
          <div className="text-center pb-1">
            <p className="text-lg font-bold text-gray-300">+</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-500 mb-1 truncate">{awayTeam}</p>
            <p className="text-3xl font-black text-rose-500 font-mono">
              {cards.expected_cards_away.toFixed(1)}
            </p>
          </div>
        </div>

        <div className="rounded-lg bg-yellow-50 ring-1 ring-yellow-200 p-3 text-center">
          <p className="text-xs text-gray-500 mb-0.5">Total esperado</p>
          <p className="text-2xl font-black text-yellow-600 font-mono">
            {cards.expected_cards_total.toFixed(1)}
          </p>
        </div>
      </div>

    </div>
  )
}
