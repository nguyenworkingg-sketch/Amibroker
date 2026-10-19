export type SignalStatus = 'NEW' | 'CONTINUING' | 'RETURNING' | 'DROPPED' | 'UNKNOWN'

export interface MetricDef {
  key: string
  label: string
  unit?: string | null
}

export interface StrategyMeta {
  id: string
  name: string
  description: string
  enabled: boolean
  version: string
  source_afl: string[]
  adapter_afl: string | null
  apx: string | null
  two_pass: boolean
  supports_backfill: boolean
  pass_rule: { column: string; op: string; value: number } | null
  score_name: string
  scoring: string
  state_labels: Record<string, string>
  metrics: MetricDef[]
  connected: boolean
  last_session: string | null
  last_generated_at: string | null
  last_count: number | null
  sessions_recorded: number
  first_session: string | null
}

export interface Meta {
  schema_version: number
  demo: boolean
  latest_session: string | null
  sessions: string[]
  strategies: StrategyMeta[]
  liquidity_default_bil: number
  built_at: string | null
  has_market_data: boolean
  sector_names: string[]
}

export interface SignalRecord {
  ticker: string
  strategy_id: string
  signal_date: string
  state_code: number | null
  state: string | null
  strategy_score: number | null
  strategy_rank: number | null
  name: string | null
  exchange: string | null
  sector: string | null
  close: number | null
  ret_1d: number | null
  ret_5d: number | null
  ret_20d: number | null
  avg_trading_value_20: number | null
  relative_strength_score: number | null
  additional_metrics: Record<string, number | string | boolean | null>
  signal_status: SignalStatus
  previous_rank: number | null
  rank_change: number | null
  streak: number
  episode_start: string
  first_seen: string
  n_strategies: number
  strategies: string[]
  multi_streak: number
}

export interface DroppedRecord {
  ticker: string
  strategy_id: string
  signal_status: 'DROPPED'
  last_signal_date: string
  previous_rank: number | null
  strategy_score: number | null
  state: string | null
  streak: number | null
  episode_start: string | null
  name: string | null
  exchange: string | null
  sector: string | null
}

export interface StrategySessionInfo {
  available: boolean
  compared_to?: string | null
  gap?: number | null
  origin?: string
  generated_at?: string
  data_asof?: string
  total?: number
  new?: number
  returning?: number
  continuing?: number
  unknown?: number
  dropped?: number
}

export interface SessionDoc {
  session: string
  benchmark: { close?: number; ret_1d?: number | null; ret_5d?: number | null; ret_20d?: number | null; ret_63d?: number | null }
  strategies: Record<string, StrategySessionInfo>
  records: SignalRecord[]
  dropped: DroppedRecord[]
}

export interface SessionSummary {
  session: string
  strategies_available: string[]
  unique_tickers: number
  new: number
  returning: number
  continuing: number
  unknown: number
  dropped: number
  multi2: number
  multi3: number
  by_strategy: Record<string, { total: number; new: number; returning: number; continuing: number; unknown: number; dropped: number; origin: string }>
}

export interface SummaryDoc {
  latest: SessionSummary | null
  sessions: SessionSummary[]
}

export interface RunStep {
  name: string
  status: string
  strategy?: string
  session?: string
  records?: number
  seconds?: number
  message?: string | null
}

export interface RunRecord {
  run_id: string
  kind: string
  started_at: string
  finished_at: string | null
  session: string | null
  result: string
  message: string | null
  steps: RunStep[]
}

export interface StatusDoc {
  runs: RunRecord[]
  strategies: Record<string, { last_status?: string; last_run_at?: string; last_message?: string | null; last_success_session?: string; last_success_at?: string; last_records?: number; last_error?: string | null }>
  last_success?: { run_id: string; at: string; session: string; kind: string }
  last_run?: Omit<RunRecord, 'steps'>
  last_publication?: { at: string; session: string | null }
}

export interface HistoryIndex {
  columns: string[]
  rows: (string | number | null)[][]
}

export interface ForwardStat {
  n: number
  mean: number | null
  median: number | null
  win_rate: number | null
}

export interface ForwardDoc {
  entry_rule: string
  cost_pct: number
  horizons: string[]
  available: boolean
  strategies: Record<string, Record<string, { gross: ForwardStat; net: ForwardStat; bench: ForwardStat; excess: ForwardStat; pending: number }>>
}

export interface ForwardResult {
  gross: number
  net: number
  bench: number
  excess: number
  entry_date: string
  exit_date: string
}

export interface TickerDoc {
  ticker: string
  name: string | null
  exchange: string | null
  sector: string | null
  timeline: { date: string; s: Record<string, [number | null, number | null, SignalStatus, string | null]> }[]
  rs: [string, number][]
  close: [string, number][]
  episodes: { strategy_id: string; start: string; status: SignalStatus; score: number | null; origin: string; forward: Record<string, ForwardResult | null> }[]
}

export interface BreadthGroup {
  n: number
  above_ma20: number | null
  above_ma50: number | null
  above_ma200: number | null
  n_ma20: number
  n_ma50: number
  n_ma200: number
  advancers: number
  decliners: number
  new_high_52w: number
}

export interface BreadthDoc {
  series: ({ date: string } & Record<'ALL' | 'HOSE' | 'HNX' | 'UPCoM', BreadthGroup>)[]
}

export interface SectorRow {
  ticker: string
  sector: string
  close: number | null
  rsz: number | null
  rsmom: number | null
  ret5: number | null
  ret20: number | null
  ret60: number | null
  excess63: number | null
  quadrant: string | null
  rank?: number
  prev_rank: number | null
  rank_5: number | null
  signals: Record<string, number>
  signals_total: number
}

export interface SectorsDoc {
  available: boolean
  latest: string | null
  signals_session?: string | null
  rows: SectorRow[]
  history: Record<string, [string, number | null, number | null, number | null][]>
}

export interface SignalTrendDoc {
  series: ({ session: string; unique: number; new: number; dropped: number } & Record<string, number | string>)[]
}

export interface BacktestDoc {
  available: boolean
  reports: {
    id: string
    strategy_id: string
    title: string
    source: string
    period: string
    imported_at: string
    metrics: Record<string, number | null>
    benchmark?: Record<string, number | null>
  }[]
}
