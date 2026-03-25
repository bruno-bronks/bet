import { useState } from 'react'
import { api } from '../api/client'
import type { PredictRequest, PredictResponse } from '../types/prediction'

interface State {
  data: PredictResponse | null
  loading: boolean
  error: string | null
}

export function usePrediction() {
  const [state, setState] = useState<State>({ data: null, loading: false, error: null })

  const predict = async (req: PredictRequest) => {
    setState({ data: null, loading: true, error: null })
    try {
      const data = await api.predict(req)
      setState({ data, loading: false, error: null })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Falha na predição'
      setState({ data: null, loading: false, error: msg })
    }
  }

  const reset = () => setState({ data: null, loading: false, error: null })

  return { ...state, predict, reset }
}
