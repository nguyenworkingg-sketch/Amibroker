import { useEffect, useState } from 'react'
import type {
  BacktestDoc, BreadthDoc, TopRsDoc, ForwardDoc, HistoryIndex, Meta, SectorsDoc, SessionDoc, SignalTrendDoc, StatusDoc, SummaryDoc, TickerDoc,
} from './types'

const BASE = `${import.meta.env.BASE_URL}data/`
const cache = new Map<string, Promise<unknown>>()

export class NotFound extends Error {}

/** Tai JSON (co cache trong phien). 404 -> NotFound de trang hien trang thai trong ro rang. */
export function fetchJson<T>(path: string, fresh = false): Promise<T> {
  if (!fresh && cache.has(path)) return cache.get(path) as Promise<T>
  const p = fetch(BASE + path, { cache: path === 'meta.json' || path === 'status.json' ? 'no-cache' : 'default' }).then(async (r) => {
    if (r.status === 404) throw new NotFound(path)
    if (!r.ok) throw new Error(`HTTP ${r.status} khi tải ${path}`)
    return (await r.json()) as T
  })
  cache.set(path, p)
  p.catch(() => cache.delete(path))
  return p
}

export const api = {
  meta: () => fetchJson<Meta>('meta.json'),
  summary: () => fetchJson<SummaryDoc>('latest/summary.json'),
  session: (d: string) => fetchJson<SessionDoc>(`sessions/${d}.json`),
  status: () => fetchJson<StatusDoc>('status.json'),
  history: () => fetchJson<HistoryIndex>('history/index.json'),
  ticker: (t: string) => fetchJson<TickerDoc>(`tickers/${encodeURIComponent(t)}.json`),
  breadth: () => fetchJson<BreadthDoc>('market/breadth.json'),
  sectors: () => fetchJson<SectorsDoc>('market/sectors.json'),
  signalTrend: () => fetchJson<SignalTrendDoc>('market/signal_trend.json'),
  forward: () => fetchJson<ForwardDoc>('performance/forward.json'),
  backtest: () => fetchJson<BacktestDoc>('backtest/index.json'),
  topRs: () => fetchJson<TopRsDoc>('toprs/latest.json'),
}

export interface Loadable<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

export function useLoad<T>(fn: (() => Promise<T>) | null, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ data: null, error: null, loading: !!fn })
  useEffect(() => {
    if (!fn) {
      setState({ data: null, error: null, loading: false })
      return
    }
    let alive = true
    setState((s) => ({ data: s.data, error: null, loading: true }))
    fn().then(
      (data) => alive && setState({ data, error: null, loading: false }),
      (error: Error) => alive && setState({ data: null, error, loading: false }),
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}
