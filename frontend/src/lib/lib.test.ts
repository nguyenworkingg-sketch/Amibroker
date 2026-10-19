import { describe, expect, it } from 'vitest'
import { applyFilters, type Filters } from '../pages/Exploration'
import { toCsv } from './csv'
import { bil, num, pct } from './format'
import { expectedSession, freshness, weekdaysBetween } from './freshness'
import { attachPrevRank, buildMulti, percentile } from './ranking'
import { href, parseHash } from './router'
import type { SignalRecord } from './types'

function rec(p: Partial<SignalRecord>): SignalRecord {
  return {
    ticker: 'AAA', strategy_id: 'VCP', signal_date: '2026-10-16', state_code: 1, state: null, strategy_score: 50, strategy_rank: 1,
    name: null, exchange: 'HOSE', sector: null, close: 10, ret_1d: null, ret_5d: null, ret_20d: null, avg_trading_value_20: 10,
    relative_strength_score: null, additional_metrics: {}, signal_status: 'NEW', previous_rank: null, rank_change: null, streak: 1,
    episode_start: '2026-10-16', first_seen: '2026-10-16', n_strategies: 1, strategies: ['VCP'], multi_streak: 0, ...p,
  }
}

describe('freshness (lich phien thu 2-6, gio VN)', () => {
  it('truoc 18:30 thi phien du kien la phien hom truoc', () => {
    // Thu 2 19/10/2026 10:00 gio VN = 03:00 UTC
    expect(expectedSession(new Date('2026-10-19T03:00:00Z'))).toBe('2026-10-16')
    // Thu 2 19:00 gio VN
    expect(expectedSession(new Date('2026-10-19T12:00:00Z'))).toBe('2026-10-19')
    // Chu nhat
    expect(expectedSession(new Date('2026-10-18T12:00:00Z'))).toBe('2026-10-16')
  })
  it('do tre tinh theo phien, khong theo ngay lich', () => {
    expect(weekdaysBetween('2026-10-16', '2026-10-19')).toBe(1)
    expect(freshness('2026-10-16', new Date('2026-10-19T03:00:00Z')).level).toBe('fresh')
    expect(freshness('2026-10-14', new Date('2026-10-19T03:00:00Z')).level).toBe('stale')
    expect(freshness(null).level).toBe('none')
  })
})

describe('format', () => {
  it('thieu du lieu hien dau gach, khong hien 0', () => {
    expect(num(null)).toBe('—')
    expect(pct(undefined)).toBe('—')
    expect(bil(null)).toBe('—')
    expect(pct(1.234, 1)).toBe('+1,2%')
    expect(num(1234.5, 1)).toBe('1.234,5')
  })
})

describe('ranking da phuong phap', () => {
  it('phan vi hang va diem dong thuan minh bach', () => {
    expect(percentile(1, 5)).toBe(100)
    expect(percentile(5, 5)).toBe(0)
    expect(percentile(1, 1)).toBe(100)
    expect(percentile(null, 5)).toBeNull()
    const rows = buildMulti(
      [
        rec({ ticker: 'AAA', strategy_id: 'VCP', strategy_rank: 1 }),
        rec({ ticker: 'BBB', strategy_id: 'VCP', strategy_rank: 2 }),
        rec({ ticker: 'BBB', strategy_id: 'RS', strategy_rank: 1 }),
        rec({ ticker: 'CCC', strategy_id: 'RS', strategy_rank: 2 }),
      ],
      ['VCP', 'RS'],
    )
    expect(rows.map((r) => r.ticker)).toEqual(['BBB', 'AAA', 'CCC'])
    expect(rows[0].n).toBe(2)
    expect(rows[0].consensus).toBe(50) // (0 + 100) / 2
    const prev = buildMulti([rec({ ticker: 'AAA' }), rec({ ticker: 'BBB', strategy_rank: 2 })], ['VCP', 'RS'])
    const withPrev = attachPrevRank(rows, prev)
    expect(withPrev[0].rank_change).toBe(1) // BBB: hang 2 -> 1
    expect(withPrev[2].prev_rank).toBeNull()
  })
})

describe('bo loc Daily Exploration', () => {
  const base: Filters = { strategy: 'ALL', q: '', exchange: 'ALL', sector: 'ALL', status: 'ALL', minLiq: 2, minStrat: 1 }
  const rows = [
    rec({ ticker: 'AAA', avg_trading_value_20: 5 }),
    rec({ ticker: 'BBB', avg_trading_value_20: 1 }),
    rec({ ticker: 'CCC', avg_trading_value_20: null }),
    rec({ ticker: 'DDD', strategy_id: 'RS', signal_status: 'CONTINUING', n_strategies: 2, exchange: 'HNX' }),
  ]
  it('GTGD thieu khong bi coi la 0 ma duoc dem rieng', () => {
    const r = applyFilters(rows, base)
    expect(r.rows.map((x) => x.ticker)).toEqual(['AAA', 'DDD'])
    expect(r.hiddenNoLiq).toBe(1)
    expect(applyFilters(rows, { ...base, minLiq: 0 }).rows.length).toBe(4)
  })
  it('loc phuong phap, trang thai, san, so phuong phap, tim kiem', () => {
    expect(applyFilters(rows, { ...base, strategy: 'RS' }).rows.map((x) => x.ticker)).toEqual(['DDD'])
    expect(applyFilters(rows, { ...base, status: 'NEWISH' }).rows.map((x) => x.ticker)).toEqual(['AAA'])
    expect(applyFilters(rows, { ...base, exchange: 'HNX' }).rows.map((x) => x.ticker)).toEqual(['DDD'])
    expect(applyFilters(rows, { ...base, minStrat: 2 }).rows.map((x) => x.ticker)).toEqual(['DDD'])
    expect(applyFilters(rows, { ...base, q: 'aa' }).rows.map((x) => x.ticker)).toEqual(['AAA'])
  })
})

describe('csv + router', () => {
  it('CSV co BOM, o trong cho null, escape dau phay', () => {
    const s = toCsv([{ a: 'x,y', b: null as number | null }], [{ header: 'A', value: (r) => r.a }, { header: 'B', value: (r) => r.b }])
    expect(s).toBe('﻿A,B\r\n"x,y",\r\n')
  })
  it('hash route', () => {
    const r = parseHash('#/exploration?s=VCP&d=2026-10-16')
    expect(r.path).toBe('/exploration')
    expect(r.query.get('s')).toBe('VCP')
    expect(href('/stock', { t: 'FPT', x: null })).toBe('#/stock?t=FPT')
  })
})
