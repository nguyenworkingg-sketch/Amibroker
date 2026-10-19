import type { SignalRecord } from './types'

/** Diem dong thuan (minh bach):
 *  1) So phuong phap dat (uu tien chinh).
 *  2) Phan vi hang trong tung phuong phap: p = 100 x (N - hang) / (N - 1) (N = so ma dat cua phuong phap do;
 *     N = 1 -> p = 100). Diem thanh phan = trung binh p cua cac phuong phap dat.
 *  KHONG cong diem tho cua cac AFL khac nhau (thang do khac nhau). Khong phai du bao loi nhuan.
 */
export interface MultiRow {
  ticker: string
  name: string | null
  exchange: string | null
  sector: string | null
  n: number
  strategies: string[]
  components: { strategy_id: string; rank: number | null; of: number; pctile: number | null; score: number | null; status: string }[]
  consensus: number | null
  close: number | null
  ret_5d: number | null
  ret_20d: number | null
  avg_trading_value_20: number | null
  relative_strength_score: number | null
  multi_streak: number
  has_new: boolean
  rank: number
  prev_rank: number | null
  rank_change: number | null
}

export function percentile(rank: number | null, n: number): number | null {
  if (rank === null || rank === undefined || n <= 0) return null
  if (n === 1) return 100
  return Math.round((1000 * (n - rank)) / (n - 1)) / 10
}

export function buildMulti(records: SignalRecord[], strategyOrder: string[]): MultiRow[] {
  const counts = new Map<string, number>()
  for (const r of records) counts.set(r.strategy_id, (counts.get(r.strategy_id) ?? 0) + 1)
  const by = new Map<string, SignalRecord[]>()
  for (const r of records) {
    const a = by.get(r.ticker)
    if (a) a.push(r)
    else by.set(r.ticker, [r])
  }
  const rows: MultiRow[] = []
  for (const [ticker, rs] of by) {
    rs.sort((a, b) => strategyOrder.indexOf(a.strategy_id) - strategyOrder.indexOf(b.strategy_id))
    const comps = rs.map((r) => {
      const of = counts.get(r.strategy_id) ?? 0
      return { strategy_id: r.strategy_id, rank: r.strategy_rank, of, pctile: percentile(r.strategy_rank, of), score: r.strategy_score, status: r.signal_status }
    })
    const ps = comps.map((c) => c.pctile).filter((x): x is number => x !== null)
    const f = rs[0]
    rows.push({
      ticker, name: f.name, exchange: f.exchange, sector: f.sector, n: rs.length, strategies: rs.map((r) => r.strategy_id),
      components: comps, consensus: ps.length ? Math.round((10 * ps.reduce((a, b) => a + b, 0)) / ps.length) / 10 : null,
      close: f.close, ret_5d: f.ret_5d, ret_20d: f.ret_20d, avg_trading_value_20: f.avg_trading_value_20,
      relative_strength_score: f.relative_strength_score, multi_streak: f.multi_streak,
      has_new: rs.some((r) => r.signal_status === 'NEW' || r.signal_status === 'RETURNING'),
      rank: 0, prev_rank: null, rank_change: null,
    })
  }
  rows.sort((a, b) => b.n - a.n || (b.consensus ?? -1) - (a.consensus ?? -1) || a.ticker.localeCompare(b.ticker))
  rows.forEach((r, i) => (r.rank = i + 1))
  return rows
}

/** Gan hang phien truoc + thay doi hang (duong = tang hang). */
export function attachPrevRank(cur: MultiRow[], prev: MultiRow[] | null): MultiRow[] {
  if (!prev) return cur
  const m = new Map(prev.map((r) => [r.ticker, r.rank]))
  return cur.map((r) => {
    const p = m.get(r.ticker) ?? null
    return { ...r, prev_rank: p, rank_change: p === null ? null : p - r.rank }
  })
}
