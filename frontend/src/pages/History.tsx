import { useMemo, useState } from 'react'
import type { PageProps } from '../App'
import { DataTable, numCol, textCol } from '../components/DataTable'
import { Card, Empty, LoadError, Loading, Note, PageTitle, Select, SHORT, StrategyChip, TickerLink } from '../components/ui'
import { api, useLoad } from '../lib/data'
import { dateVN, num, pct, signClass } from '../lib/format'
import { type Route, setQuery } from '../lib/router'

interface HRow {
  strategy_id: string
  ticker: string
  first_signal: string
  last_signal: string
  sessions: number
  current_streak: number
  reappearances: number
  current_score: number | null
  current_rank: number | null
  active: number
}

export default function History({ meta, route }: PageProps & { route: Route }) {
  const hist = useLoad(() => api.history(), [])
  const fwd = useLoad(() => api.forward().catch(() => null), [])
  const s = route.query.get('s') ?? 'ALL'
  const act = route.query.get('a') ?? 'ALL'
  const [search, setSearch] = useState('')
  const [basis, setBasis] = useState<'gross' | 'net' | 'excess'>('excess')
  const rows = useMemo<HRow[]>(() => {
    if (!hist.data) return []
    const c = hist.data.columns
    return hist.data.rows.map((r) => Object.fromEntries(c.map((k, i) => [k, r[i]])) as unknown as HRow)
  }, [hist.data])
  const filtered = rows.filter(
    (r) => (s === 'ALL' || r.strategy_id === s) && (act === 'ALL' || (act === '1' ? r.active === 1 : r.active === 0)) && (!search || r.ticker.includes(search.toUpperCase())),
  )
  return (
    <div className="space-y-5">
      <PageTitle title="Signal History" sub="Lịch sử ghi nhận tín hiệu theo phương pháp và mã, cùng hiệu suất sau tín hiệu." />
      <Card title="Hiệu suất sau tín hiệu (nghiên cứu)" right={
        <Select label="Chỉ số" value={basis} onChange={setBasis} options={[{ value: 'excess', label: 'Vượt VN-Index' }, { value: 'gross', label: 'Lợi suất gộp' }, { value: 'net', label: 'Sau phí' }]} />
      }>
        {fwd.loading ? <Loading /> : !fwd.data || !fwd.data.available ? (
          <Empty title="Đang chờ dữ liệu giá">Cần dữ liệu giá EOD trên máy chạy exporter để tính hiệu suất sau tín hiệu.</Empty>
        ) : (
          <>
            <div className="overflow-auto">
              <table className="dt">
                <thead>
                  <tr>
                    <th>Phương pháp</th>
                    {fwd.data.horizons.map((h) => <th key={h} className="r" colSpan={1}>{h} phiên</th>)}
                  </tr>
                </thead>
                <tbody>
                  {meta.strategies.map((st) => {
                    const r = fwd.data!.strategies[st.id]
                    return (
                      <tr key={st.id}>
                        <td><StrategyChip id={st.id} /></td>
                        {fwd.data!.horizons.map((h) => {
                          const x = r?.[h]
                          const v = x?.[basis]
                          return (
                            <td key={h} className="r num" title={x ? `n = ${v?.n} · trung vị ${pct(v?.median ?? null, 2)} · chưa đủ cửa sổ: ${x.pending}` : ''}>
                              {!v || v.n === 0 ? <span className="text-muted">—{x?.pending ? ` (chờ ${x.pending})` : ''}</span> : (
                                <>
                                  <span className={signClass(v.mean)}>{pct(v.mean, 2)}</span>
                                  <span className="ml-1 text-muted">· {num(v.win_rate, 0)}% · n={v.n}</span>
                                </>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 space-y-1 text-[12px] text-muted">
              <div>Ô = trung bình · tỷ lệ dương · số đợt tín hiệu. Chỉ tính đợt tín hiệu <b>Mới / Quay lại</b> (không đếm lặp các phiên tiếp diễn). {fwd.data.entry_rule} Sau phí: trừ {num(fwd.data.cost_pct, 2)}% chi phí khứ hồi.</div>
              <div>Cửa sổ chưa đủ số phiên thì không tính (ghi “chờ”). Phần lớn lịch sử là <b>tái tạo</b> bằng cách chạy lại Exploration trên dữ liệu quá khứ (giá đã điều chỉnh, danh sách ngành hiện tại) — dùng để nghiên cứu, không phải kết quả giao dịch thực tế, chưa kiểm định ngoài mẫu.</div>
            </div>
          </>
        )}
      </Card>
      <Card title="Lịch sử theo mã">
        {hist.loading ? <Loading /> : hist.error ? <LoadError error={hist.error} /> : (
          <DataTable<HRow>
            data={filtered}
            rowKey={(r) => `${r.strategy_id}:${r.ticker}`}
            initialSort={[{ id: 'last', desc: true }, { id: 'sessions', desc: true }]}
            toolbar={
              <>
                <input className="inp w-32" placeholder="Tìm mã…" value={search} onChange={(e) => setSearch(e.target.value)} />
                <Select label="Phương pháp" value={s} onChange={(v) => setQuery(route, { s: v === 'ALL' ? null : v })} options={[{ value: 'ALL', label: 'Tất cả' }, ...meta.strategies.map((x) => ({ value: x.id, label: SHORT[x.id] ?? x.id }))]} />
                <Select label="Hiện tại" value={act} onChange={(v) => setQuery(route, { a: v === 'ALL' ? null : v })} options={[{ value: 'ALL', label: 'Tất cả' }, { value: '1', label: 'Đang đạt' }, { value: '0', label: 'Không còn đạt' }]} />
              </>
            }
            columns={[
              textCol('ticker', 'Mã', (r) => r.ticker, (r) => <TickerLink t={r.ticker} />),
              textCol('strategy', 'Phương pháp', (r) => r.strategy_id, (r) => <StrategyChip id={r.strategy_id} />),
              textCol('first', 'Tín hiệu đầu tiên', (r) => r.first_signal, (r) => <span className="num">{dateVN(r.first_signal)}</span>),
              textCol('last', 'Tín hiệu gần nhất', (r) => r.last_signal, (r) => <span className="num">{dateVN(r.last_signal)}</span>),
              numCol('sessions', 'Số phiên đạt', (r) => r.sessions, (v) => num(v, 0)),
              numCol('streak', 'Chuỗi hiện tại', (r) => r.current_streak, (v) => num(v, 0)),
              numCol('re', 'Số lần quay lại', (r) => r.reappearances, (v) => num(v, 0)),
              numCol('score', 'Điểm hiện tại', (r) => r.current_score, (v) => num(v, 1)),
              numCol('rank', 'Hạng hiện tại', (r) => (r.current_rank === null ? null : -r.current_rank), (_v, r) => r.current_rank ?? '—'),
              textCol('active', 'Đang đạt', (r) => (r.active ? 'Có' : 'Không')),
            ]}
          />
        )}
        <div className="mt-2 text-[12px] text-muted">Phương pháp chỉ tính được phiên cuối (RS, High Beta) bắt đầu có lịch sử từ ngày đầu chạy thật: {meta.strategies.filter((x) => !x.supports_backfill).map((x) => `${SHORT[x.id]} từ ${dateVN(x.first_session)}`).join(', ')}.</div>
      </Card>
      <Note>Nguồn: snapshot của từng phiên được lưu nguyên trong kho dữ liệu (data/snapshots) để có thể kiểm tra lại.</Note>
    </div>
  )
}
