import { useMemo } from 'react'
import type { PageProps } from '../App'
import { DataTable, numCol, textCol } from '../components/DataTable'
import { Card, Empty, LoadError, Loading, Note, PageTitle, Select, SHORT, StatusBadge, TickerLink } from '../components/ui'
import { downloadCsv, toCsv } from '../lib/csv'
import { api, useLoad } from '../lib/data'
import { bil, dateVN, num, pct, signClass } from '../lib/format'
import { attachPrevRank, buildMulti, type MultiRow } from '../lib/ranking'
import { type Route, setQuery } from '../lib/router'

export default function Ranking({ meta, route }: PageProps & { route: Route }) {
  const q = route.query
  const date = q.get('d') ?? meta.latest_session ?? ''
  const idx = meta.sessions.indexOf(date)
  const prevDate = idx >= 0 ? meta.sessions[idx + 1] : undefined
  const minN = Number(q.get('m') ?? 2)
  const must = q.get('inc') ?? 'ALL'
  const ex = q.get('ex') ?? 'ALL'
  const minLiq = q.has('liq') ? Number(q.get('liq')) : meta.liquidity_default_bil
  const order = meta.strategies.map((s) => s.id)
  const cur = useLoad(() => (date ? api.session(date) : Promise.resolve(null)), [date])
  const prev = useLoad(() => (prevDate ? api.session(prevDate) : Promise.resolve(null)), [prevDate])
  const set = (p: Record<string, string | number | null>) => setQuery(route, p)

  const rows = useMemo(() => {
    if (!cur.data) return []
    const c = buildMulti(cur.data.records, order)
    const p = prev.data ? buildMulti(prev.data.records, order) : null
    return attachPrevRank(c, p).filter(
      (r) => r.n >= minN && (must === 'ALL' || r.strategies.includes(must)) && (ex === 'ALL' || r.exchange === ex) &&
        (minLiq <= 0 || (r.avg_trading_value_20 !== null && r.avg_trading_value_20 >= minLiq)),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur.data, prev.data, minN, must, ex, minLiq])

  if (!meta.latest_session) return <Empty title="Chưa có dữ liệu" />
  const avail = cur.data ? Object.entries(cur.data.strategies).filter(([, v]) => v.available).map(([k]) => k) : []
  return (
    <div className="space-y-4">
      <PageTitle
        title="Strategy Ranking"
        sub={`Cổ phiếu cùng đạt nhiều phương pháp độc lập — phiên ${dateVN(date)}`}
        right={
          <label className="flex items-center gap-1.5 text-[12.5px] text-muted">
            Phiên
            <select className="inp" value={date} onChange={(e) => set({ d: e.target.value === meta.latest_session ? null : e.target.value })}>
              {meta.sessions.map((s) => <option key={s} value={s}>{dateVN(s)}</option>)}
            </select>
          </label>
        }
      />
      <Note>
        <b>Cách xếp hạng:</b> ưu tiên <b>số phương pháp đạt</b>; cùng số phương pháp thì xếp theo <b>điểm đồng thuận</b> = trung bình phân vị hạng của mã
        trong từng phương pháp đạt (phân vị = 100 × (N − hạng) / (N − 1), N = số mã đạt của phương pháp đó). Không cộng điểm thô của các AFL khác nhau
        vì thang đo khác nhau. Đây là thứ tự sàng lọc, <b>chưa được kiểm định ngoài mẫu</b> và không phải dự báo lợi nhuận.
        {cur.data && <> Phiên này có dữ liệu của {avail.length}/{order.length} phương pháp: {avail.map((a) => SHORT[a] ?? a).join(', ')}.</>}
      </Note>
      {cur.loading ? <Loading /> : cur.error ? <LoadError error={cur.error} /> : (
        <Card>
          <DataTable<MultiRow>
            data={rows}
            rowKey={(r) => r.ticker}
            initialSort={[{ id: 'rank', desc: true }]}
            toolbar={
              <>
                <Select label="Số phương pháp ≥" value={String(minN)} onChange={(v) => set({ m: v === '2' ? null : v })} options={['1', '2', '3', '4', '5'].map((x) => ({ value: x, label: x }))} />
                <Select label="Phải gồm" value={must} onChange={(v) => set({ inc: v === 'ALL' ? null : v })} options={[{ value: 'ALL', label: 'Bất kỳ' }, ...order.map((o) => ({ value: o, label: SHORT[o] ?? o }))]} />
                <Select label="Sàn" value={ex} onChange={(v) => set({ ex: v === 'ALL' ? null : v })} options={[{ value: 'ALL', label: 'Tất cả' }, { value: 'HOSE', label: 'HOSE' }, { value: 'HNX', label: 'HNX' }, { value: 'UPCoM', label: 'UPCoM' }]} />
                <label className="flex items-center gap-1.5 text-[12.5px] text-muted">
                  GTGD20 ≥
                  <input className="inp w-16" type="number" min={0} step={0.5} value={minLiq} onChange={(e) => set({ liq: e.target.value })} /> tỷ
                </label>
                <button className="btn" onClick={() => downloadCsv(`ranking_${date}.csv`, toCsv(rows, [
                  { header: 'Hang', value: (r) => r.rank }, { header: 'HangTruoc', value: (r) => r.prev_rank }, { header: 'Ma', value: (r) => r.ticker },
                  { header: 'San', value: (r) => r.exchange }, { header: 'Nganh', value: (r) => r.sector }, { header: 'SoPhuongPhap', value: (r) => r.n },
                  { header: 'ToHop', value: (r) => r.strategies.join('+') }, { header: 'DiemDongThuan', value: (r) => r.consensus },
                  { header: 'ChiTiet', value: (r) => r.components.map((c) => `${c.strategy_id}:${c.rank}/${c.of}`).join(' ') },
                  { header: 'RS', value: (r) => r.relative_strength_score }, { header: 'GTGD20Ty', value: (r) => r.avg_trading_value_20 },
                  { header: 'ChuoiPhienDongThuan', value: (r) => r.multi_streak },
                ]))}>Tải CSV</button>
              </>
            }
            columns={[
              numCol('rank', 'Hạng', (r) => -r.rank, (_v, r) => r.rank),
              numCol('dr', 'Δ hạng', (r) => r.rank_change, (v, r) => r.prev_rank === null ? <span className="text-muted">mới</span> : <span className={signClass(v)}>{v! > 0 ? `▲${v}` : v! < 0 ? `▼${-v!}` : '0'}</span>, 'So với xếp hạng phiên trước'),
              textCol('ticker', 'Mã', (r) => r.ticker, (r) => <TickerLink t={r.ticker} />),
              textCol('exchange', 'Sàn', (r) => r.exchange),
              textCol('sector', 'Ngành', (r) => r.sector),
              numCol('n', 'Số PP', (r) => r.n, (v) => num(v, 0)),
              textCol('combo', 'Tổ hợp phương pháp (hạng/số mã đạt)', (r) => r.strategies.join('+'), (r) => (
                <div className="flex flex-wrap gap-1">
                  {r.components.map((c) => (
                    <span key={c.strategy_id} className="tag" title={`Điểm ${num(c.score, 1)} · phân vị ${num(c.pctile, 0)}`}>
                      {SHORT[c.strategy_id] ?? c.strategy_id} <span className="num ml-1 text-muted">{c.rank ?? '–'}/{c.of}</span>
                      {(c.status === 'NEW' || c.status === 'RETURNING') && <span className="ml-1 text-accent">●</span>}
                    </span>
                  ))}
                </div>
              )),
              numCol('cons', 'Điểm đồng thuận', (r) => r.consensus, (v) => num(v, 1), 'Trung bình phân vị hạng (0–100)'),
              numCol('rs', 'RS', (r) => r.relative_strength_score, (v) => num(v, 0)),
              numCol('liq', 'GTGD20', (r) => r.avg_trading_value_20, (v) => bil(v)),
              numCol('r20', '% 20P', (r) => r.ret_20d, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
              numCol('streak', 'Chuỗi phiên', (r) => r.multi_streak, (v) => num(v, 0), 'Số phiên liên tiếp đạt ≥ 2 phương pháp'),
              textCol('new', 'Có tín hiệu mới', (r) => (r.has_new ? 'x' : null), (r) => (r.has_new ? <StatusBadge s="NEW" /> : '')),
            ]}
          />
        </Card>
      )}
    </div>
  )
}
