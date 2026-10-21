import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import type { PageProps } from '../App'
import { DataTable, numCol, textCol } from '../components/DataTable'
import { Card, Empty, LoadError, Loading, Note, PageTitle, Select, SHORT, Stat, StatusBadge, StrategyChip, TickerLink } from '../components/ui'
import { downloadCsv, toCsv } from '../lib/csv'
import { api, useLoad } from '../lib/data'
import { bil, dateTimeVN, dateVN, num, ORIGIN_LABEL, pct, price, signClass, STATUS_LABEL } from '../lib/format'
import { type Route, setQuery } from '../lib/router'
import type { DroppedRecord, MetricDef, SignalRecord, StrategyMeta } from '../lib/types'

export interface Filters {
  strategy: string
  q: string
  exchange: string
  sector: string
  status: string
  minLiq: number
  minStrat: number
}

/** Loc thuan (dung chung + kiem thu). Ma thieu GTGD20 KHONG duoc coi la 0: bi an khi dat nguong > 0 va duoc dem rieng. */
export function applyFilters(rows: SignalRecord[], f: Filters): { rows: SignalRecord[]; hiddenNoLiq: number } {
  let hiddenNoLiq = 0
  const q = f.q.trim().toUpperCase()
  const out = rows.filter((r) => {
    if (f.strategy !== 'ALL' && r.strategy_id !== f.strategy) return false
    if (q && !r.ticker.includes(q) && !(r.name ?? '').toUpperCase().includes(q)) return false
    if (f.exchange !== 'ALL' && r.exchange !== f.exchange) return false
    if (f.sector !== 'ALL' && (r.sector ?? '') !== (f.sector === '_none' ? '' : f.sector)) return false
    if (f.status === 'NEWISH' ? !(r.signal_status === 'NEW' || r.signal_status === 'RETURNING') : f.status !== 'ALL' && r.signal_status !== f.status) return false
    if (r.n_strategies < f.minStrat) return false
    if (f.minLiq > 0) {
      if (r.avg_trading_value_20 === null) {
        hiddenNoLiq++
        return false
      }
      if (r.avg_trading_value_20 < f.minLiq) return false
    }
    return true
  })
  return { rows: out, hiddenNoLiq }
}

function metricCell(v: number | string | boolean | null | undefined, m: MetricDef) {
  if (v === null || v === undefined) return '—'
  if (m.unit === 'bool') return v ? 'Có' : 'Không'
  if (typeof v === 'string') return v
  if (typeof v === 'boolean') return v ? 'Có' : 'Không'
  return num(v, Number.isInteger(v) ? 0 : Math.abs(v) >= 100 ? 1 : 2)
}

export function signalColumns(meta: StrategyMeta[], single: StrategyMeta | null): ColumnDef<SignalRecord, unknown>[] {
  const names = Object.fromEntries(meta.map((s) => [s.id, s.name]))
  const cols: ColumnDef<SignalRecord, unknown>[] = [
    textCol('ticker', 'Mã', (r) => r.ticker, (r) => <TickerLink t={r.ticker} />),
    textCol('name', 'Tên', (r) => r.name, (r) => <span className="block max-w-56 truncate" title={r.name ?? ''}>{r.name ?? '—'}</span>),
    textCol('exchange', 'Sàn', (r) => r.exchange),
    textCol('sector', 'Ngành', (r) => r.sector),
    textCol('strategy', 'Phương pháp', (r) => r.strategy_id, (r) => <span title={names[r.strategy_id]}><StrategyChip id={r.strategy_id} /></span>),
    textCol('status', 'Tín hiệu', (r) => r.signal_status, (r) => <StatusBadge s={r.signal_status} />),
    textCol('state', 'Trạng thái', (r) => r.state),
    textCol('start', 'Ngày vào', (r) => r.episode_start, (r) => (
      <span className="num" title={r.entry_censored ? 'Đã đạt từ trước phiên đầu tiên được ghi nhận' : ''}>{r.entry_censored ? '≤ ' : ''}{dateVN(r.episode_start)}</span>
    )),
    numCol('streak', 'Số phiên', (r) => r.streak, (v) => num(v, 0), 'Số phiên liên tiếp đạt của đợt tín hiệu hiện tại'),
    numCol('entry', 'Giá vào', (r) => r.entry_price, (v) => price(v), 'Giá đóng cửa phiên bắt đầu đợt tín hiệu (nghìn đồng, đã điều chỉnh)'),
    numCol('close', 'Giá', (r) => r.close, (v) => price(v), 'Giá đóng cửa (nghìn đồng)'),
    numCol('rse', '% từ khi vào', (r) => r.ret_since_entry, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>, 'Giá hiện tại so với giá vào'),
    numCol('vse', 'VNI cùng kỳ', (r) => r.vni_since_entry, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
    numCol('xse', 'Vượt VNI', (r) => r.excess_since_entry, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>, '% từ khi vào trừ VN-Index cùng kỳ'),
    numCol('r1', '% 1P', (r) => r.ret_1d, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
    numCol('r5', '% 5P', (r) => r.ret_5d, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
    numCol('r20', '% 20P', (r) => r.ret_20d, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
    numCol('liq', 'GTGD20', (r) => r.avg_trading_value_20, (v) => bil(v), 'Giá trị giao dịch bình quân 20 phiên (tỷ đồng)'),
    numCol('rs', 'RS', (r) => r.relative_strength_score, (v) => num(v, 0), 'Phân vị lợi suất 63 phiên trong toàn thị trường (0–100)'),
    numCol('score', 'Điểm', (r) => r.strategy_score, (v) => num(v, 1), 'Điểm riêng của phương pháp (thang đo khác nhau giữa các phương pháp)'),
    numCol('rank', 'Hạng', (r) => (r.strategy_rank === null ? null : -r.strategy_rank), (_v, r) => r.strategy_rank ?? '—', 'Hạng trong danh sách đạt của phương pháp (1 = điểm cao nhất)'),
    numCol('prank', 'Hạng trước', (r) => (r.previous_rank === null ? null : -r.previous_rank), (_v, r) => r.previous_rank ?? '—'),
    numCol('dr', 'Δ hạng', (r) => r.rank_change, (v) => <span className={signClass(v)}>{v === null || v === undefined ? '—' : v > 0 ? `▲${v}` : v < 0 ? `▼${-v}` : '0'}</span>),
    numCol('nstrat', 'Số PP', (r) => r.n_strategies, (_v, r) => <span title={r.strategies.join(' + ')}>{r.n_strategies}</span>, 'Số phương pháp cùng đạt trong phiên'),
  ]
  if (single)
    for (const m of single.metrics)
      cols.push(
        m.unit === 'text' || m.unit === 'bool'
          ? textCol(`m_${m.key}`, m.label, (r) => { const v = r.additional_metrics?.[m.key]; return v === null || v === undefined ? null : String(metricCell(v, m)) })
          : numCol(`m_${m.key}`, m.label, (r) => r.additional_metrics?.[m.key] as number | null, (v) => metricCell(v, m)),
      )
  return cols
}

export function csvForSignals(rows: SignalRecord[], single: StrategyMeta | null): string {
  return toCsv(rows, [
    { header: 'Ma', value: (r) => r.ticker },
    { header: 'Ten', value: (r) => r.name },
    { header: 'San', value: (r) => r.exchange },
    { header: 'Nganh', value: (r) => r.sector },
    { header: 'PhuongPhap', value: (r) => r.strategy_id },
    { header: 'Phien', value: (r) => r.signal_date },
    { header: 'TrangThaiTinHieu', value: (r) => STATUS_LABEL[r.signal_status] },
    { header: 'TrangThai', value: (r) => r.state },
    { header: 'NgayVao', value: (r) => (r.entry_censored ? `<=${r.episode_start}` : r.episode_start) },
    { header: 'GiaVao', value: (r) => r.entry_price },
    { header: 'TuKhiVaoPct', value: (r) => r.ret_since_entry },
    { header: 'VNICungKyPct', value: (r) => r.vni_since_entry },
    { header: 'SoPhien', value: (r) => r.streak },
    { header: 'Gia', value: (r) => r.close },
    { header: 'Ret1Pct', value: (r) => r.ret_1d },
    { header: 'Ret5Pct', value: (r) => r.ret_5d },
    { header: 'Ret20Pct', value: (r) => r.ret_20d },
    { header: 'GTGD20Ty', value: (r) => r.avg_trading_value_20 },
    { header: 'RS', value: (r) => r.relative_strength_score },
    { header: 'Diem', value: (r) => r.strategy_score },
    { header: 'Hang', value: (r) => r.strategy_rank },
    { header: 'HangTruoc', value: (r) => r.previous_rank },
    { header: 'SoPhuongPhap', value: (r) => r.n_strategies },
    { header: 'CacPhuongPhap', value: (r) => r.strategies.join('+') },
    ...(single?.metrics ?? []).map((m) => ({ header: m.label, value: (r: SignalRecord) => r.additional_metrics?.[m.key] as string | number | boolean | null })),
  ])
}

export default function Exploration({ meta, route }: PageProps & { route: Route }) {
  const q = route.query
  const date = q.get('d') ?? meta.latest_session ?? ''
  const f: Filters = {
    strategy: q.get('s') ?? 'ALL',
    q: q.get('q') ?? '',
    exchange: q.get('ex') ?? 'ALL',
    sector: q.get('sec') ?? 'ALL',
    status: q.get('st') ?? 'ALL',
    minLiq: q.has('liq') ? Number(q.get('liq')) : meta.liquidity_default_bil,
    minStrat: Number(q.get('m') ?? 1),
  }
  const [search, setSearch] = useState(f.q)
  const doc = useLoad(() => (date ? api.session(date) : Promise.resolve(null)), [date])
  const single = meta.strategies.find((s) => s.id === f.strategy) ?? null
  const set = (patch: Record<string, string | number | null>) => setQuery(route, patch)

  const filtered = useMemo(() => (doc.data ? applyFilters(doc.data.records, f) : { rows: [], hiddenNoLiq: 0 }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doc.data, f.strategy, f.q, f.exchange, f.sector, f.status, f.minLiq, f.minStrat])
  const columns = useMemo(() => signalColumns(meta.strategies, single), [meta.strategies, single])
  const dropped = useMemo(
    () => (doc.data?.dropped ?? []).filter((r) => (f.strategy === 'ALL' || r.strategy_id === f.strategy) && (!f.q || r.ticker.includes(f.q.toUpperCase()))),
    [doc.data, f.strategy, f.q],
  )
  if (!meta.latest_session) return <Empty title="Chưa có phiên nào có dữ liệu Exploration" />
  const info = single ? doc.data?.strategies[single.id] : null
  const scope = doc.data ? doc.data.records.filter((r) => f.strategy === 'ALL' || r.strategy_id === f.strategy) : []
  const uniq = new Set(scope.map((r) => r.ticker)).size
  const cnt = (s: string) => scope.filter((r) => r.signal_status === s).length
  const sectors = meta.sector_names

  return (
    <div className="space-y-4">
      <PageTitle
        title="Daily Exploration"
        sub={`Kết quả lọc của phiên ${dateVN(date)}. So sánh với phiên giao dịch có dữ liệu liền trước của cùng phương pháp.`}
        right={
          <label className="flex items-center gap-1.5 text-[12.5px] text-muted">
            Phiên
            <select className="inp" value={date} onChange={(e) => set({ d: e.target.value === meta.latest_session ? null : e.target.value })}>
              {meta.sessions.map((s) => (
                <option key={s} value={s}>{dateVN(s)}</option>
              ))}
            </select>
          </label>
        }
      />
      <div className="flex flex-wrap gap-1.5" role="tablist">
        {[{ id: 'ALL', name: 'Tất cả' }, ...meta.strategies].map((s) => {
          const on = f.strategy === s.id
          const n = s.id === 'ALL' ? doc.data?.records.length : doc.data?.strategies[s.id]?.total
          return (
            <button key={s.id} role="tab" aria-selected={on} className={`btn ${on ? 'on' : ''}`} onClick={() => set({ s: s.id === 'ALL' ? null : s.id })}>
              {s.id === 'ALL' ? 'Tất cả' : SHORT[s.id] ?? s.id}
              <span className="num text-muted">{n ?? '–'}</span>
            </button>
          )
        })}
      </div>
      {doc.loading ? <Loading /> : doc.error ? <LoadError error={doc.error} /> : doc.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Mã đạt" value={uniq} tone="accent" />
            <Stat label="Mới" value={cnt('NEW')} tone="pos" />
            <Stat label="Quay lại" value={cnt('RETURNING')} />
            <Stat label="Tiếp diễn" value={cnt('CONTINUING')} sub={cnt('UNKNOWN') ? `${cnt('UNKNOWN')} chưa so sánh được` : undefined} />
            <Stat label="Không còn đạt" value={dropped.length} tone="warn" />
            <Stat label="Đạt ≥ 2 phương pháp" value={new Set(scope.filter((r) => r.n_strategies >= 2).map((r) => r.ticker)).size} />
          </div>
          {single && (
            <Card title={single.name} right={<span className="text-[12px] text-muted">Phiên bản {single.version}</span>}>
              <div className="grid gap-3 text-[13px] md:grid-cols-2">
                <div>
                  <p>{single.description}</p>
                  <p className="mt-2 text-muted"><b className="text-fg">Điểm:</b> {single.score_name}. {single.scoring}</p>
                </div>
                <div className="text-[12.5px] text-muted">
                  {info?.available ? (
                    <>
                      <div>Nguồn: <b className="text-fg">{ORIGIN_LABEL[info.origin ?? ''] ?? info.origin}</b> · chạy lúc {dateTimeVN(info.generated_at)} · dữ liệu đến {dateVN(info.data_asof)}</div>
                      <div>So sánh với phiên: {info.compared_to ? `${dateVN(info.compared_to)}${info.gap && info.gap > 1 ? ` (cách ${info.gap} phiên — thiếu dữ liệu ở giữa)` : ''}` : 'chưa có phiên trước'}</div>
                    </>
                  ) : (
                    <div className="text-warn">Phương pháp này không có dữ liệu cho phiên {dateVN(date)}{single.last_session ? ` (gần nhất: ${dateVN(single.last_session)})` : ' — chưa kết nối'}.</div>
                  )}
                  <div className="mt-1">AFL gốc: {single.source_afl.join(', ')}</div>
                </div>
              </div>
            </Card>
          )}
          <DataTable
            data={filtered.rows}
            columns={columns}
            rowKey={(r) => `${r.strategy_id}:${r.ticker}`}
            initialSort={f.strategy === 'ALL' ? [{ id: 'nstrat', desc: true }, { id: 'score', desc: true }] : [{ id: 'rank', desc: true }]}
            hiddenByDefault={['name', 'prank', 'r1', 'vse', 'r5']}
            toolbar={
              <>
                <input
                  className="inp w-36"
                  placeholder="Tìm mã…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && set({ q: search || null })}
                  onBlur={() => search !== f.q && set({ q: search || null })}
                />
                <Select label="Sàn" value={f.exchange} onChange={(v) => set({ ex: v === 'ALL' ? null : v })}
                  options={[{ value: 'ALL', label: 'Tất cả' }, { value: 'HOSE', label: 'HOSE' }, { value: 'HNX', label: 'HNX' }, { value: 'UPCoM', label: 'UPCoM' }]} />
                <Select label="Ngành" value={f.sector} onChange={(v) => set({ sec: v === 'ALL' ? null : v })}
                  options={[{ value: 'ALL', label: 'Tất cả' }, ...sectors.map((s) => ({ value: s, label: s })), { value: '_none', label: '(chưa phân ngành)' }]} />
                <Select label="Tín hiệu" value={f.status} onChange={(v) => set({ st: v === 'ALL' ? null : v })}
                  options={[{ value: 'ALL', label: 'Tất cả' }, { value: 'NEWISH', label: 'Mới + Quay lại' }, { value: 'NEW', label: 'Mới' }, { value: 'RETURNING', label: 'Quay lại' }, { value: 'CONTINUING', label: 'Tiếp diễn' }, { value: 'UNKNOWN', label: 'Chưa so sánh' }]} />
                <label className="flex items-center gap-1.5 text-[12.5px] text-muted" title="Giá trị giao dịch bình quân 20 phiên tối thiểu (tỷ đồng)">
                  GTGD20 ≥
                  <input className="inp w-16" type="number" min={0} step={0.5} value={f.minLiq} onChange={(e) => set({ liq: e.target.value === String(meta.liquidity_default_bil) ? null : e.target.value })} />
                  tỷ
                </label>
                <Select label="Số PP ≥" value={String(f.minStrat)} onChange={(v) => set({ m: v === '1' ? null : v })}
                  options={['1', '2', '3', '4'].map((x) => ({ value: x, label: x }))} />
                <button className="btn" onClick={() => downloadCsv(`exploration_${date}_${f.strategy}.csv`, csvForSignals(filtered.rows, single))}>Tải CSV</button>
              </>
            }
          />
          {filtered.hiddenNoLiq > 0 && (
            <Note>{filtered.hiddenNoLiq} dòng bị ẩn vì <b>không có dữ liệu GTGD20</b> (không coi là 0). Đặt GTGD20 ≥ 0 để xem.</Note>
          )}
          <Card title={`Không còn đạt so với phiên trước (${dropped.length})`}>
            <Note>“Không còn đạt” chỉ có nghĩa là mã không còn qua bộ lọc của phương pháp trong phiên này. <b>Đây không phải tín hiệu bán.</b></Note>
            <div className="mt-3">
              <DataTable<DroppedRecord>
                data={dropped}
                pageSize={25}
                maxHeight="40vh"
                rowKey={(r) => `${r.strategy_id}:${r.ticker}`}
                initialSort={[{ id: 'strategy', desc: false }]}
                columns={[
                  textCol('ticker', 'Mã', (r) => r.ticker, (r) => <TickerLink t={r.ticker} />),
                  textCol('strategy', 'Phương pháp', (r) => r.strategy_id, (r) => <StrategyChip id={r.strategy_id} />),
                  textCol('exchange', 'Sàn', (r) => r.exchange),
                  textCol('sector', 'Ngành', (r) => r.sector),
                  textCol('last', 'Đạt lần cuối', (r) => r.last_signal_date, (r) => <span className="num">{dateVN(r.last_signal_date)}</span>),
                  textCol('start', 'Đợt bắt đầu', (r) => r.episode_start, (r) => <span className="num">{dateVN(r.episode_start)}</span>),
                  numCol('streak', 'Số phiên đã đạt', (r) => r.streak, (v) => num(v, 0)),
                  textCol('state', 'Trạng thái cuối', (r) => r.state),
                  numCol('score', 'Điểm cuối', (r) => r.strategy_score, (v) => num(v, 1)),
                  numCol('prank', 'Hạng cuối', (r) => r.previous_rank, (v) => num(v, 0)),
                  numCol('ep', 'Giá vào', (r) => r.entry_price, (v) => price(v)),
                  numCol('lp', 'Giá phiên cuối đạt', (r) => r.last_price, (v) => price(v)),
                  numCol('rp', '% khi còn đạt', (r) => r.ret_pct, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>, 'Từ giá vào tới giá phiên cuối còn đạt'),
                  numCol('vp', 'VNI cùng kỳ', (r) => r.vni_ret_pct, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
                ]}
              />
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
