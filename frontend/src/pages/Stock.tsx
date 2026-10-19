import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PageProps } from '../App'
import { Card, Empty, LoadError, Loading, Note, PageTitle, SHORT, StatusBadge, StrategyChip } from '../components/ui'
import { api, NotFound, useLoad } from '../lib/data'
import { bil, dateVN, num, ORIGIN_LABEL, pct, price, signClass } from '../lib/format'
import { navigate, type Route } from '../lib/router'
import { STRAT_COLORS } from './Overview'

const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--border)', fontSize: 12 } }

export default function Stock({ meta, route }: PageProps & { route: Route }) {
  const t = (route.query.get('t') ?? '').toUpperCase()
  const [input, setInput] = useState(t)
  const hist = useLoad(() => api.history().catch(() => null), [])
  const doc = useLoad(() => (t ? api.ticker(t) : Promise.resolve(null)), [t])
  const latest = useLoad(() => (meta.latest_session ? api.session(meta.latest_session) : Promise.resolve(null)), [meta.latest_session])
  const sectors = useLoad(() => api.sectors().catch(() => null), [])
  const tickers = useMemo(() => [...new Set((hist.data?.rows ?? []).map((r) => String(r[1])))].sort(), [hist.data])
  const names = Object.fromEntries(meta.strategies.map((s) => [s.id, s]))

  const go = (v: string) => v.trim() && navigate('/stock', { t: v.trim().toUpperCase() })
  const search = (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); go(input) }}>
      <input className="inp w-36" list="tickers" placeholder="Nhập mã…" value={input} onChange={(e) => setInput(e.target.value)} />
      <datalist id="tickers">{tickers.map((x) => <option key={x} value={x} />)}</datalist>
      <button className="btn">Xem</button>
    </form>
  )
  if (!t) return (<div><PageTitle title="Stock Detail" sub="Chọn một mã đã từng xuất hiện trong kết quả Exploration." right={search} /><Empty title="Chưa chọn mã">{tickers.length} mã có lịch sử tín hiệu. Bấm vào mã ở bất kỳ bảng nào để mở trang này.</Empty></div>)

  const cur = (latest.data?.records ?? []).filter((r) => r.ticker === t)
  const hrows = (hist.data?.rows ?? []).filter((r) => r[1] === t)
  const d = doc.data
  const rs = d?.rs ?? []
  const rsNow = rs.at(-1)?.[1] ?? null
  const rs20 = rs.length > 20 ? rs[rs.length - 21][1] : rs[0]?.[1] ?? null
  const rankSeries = d ? d.timeline.map((p) => {
    const o: Record<string, string | number | null> = { date: p.date }
    for (const [sid, v] of Object.entries(p.s)) o[sid] = v[1]
    return o
  }) : []
  const usedStrats = d ? [...new Set(d.timeline.flatMap((p) => Object.keys(p.s)))] : []
  const secRow = d?.sector ? sectors.data?.rows.find((r) => r.sector === d.sector) : undefined
  const horizons = ['5', '10', '20', '40', '60']

  return (
    <div className="space-y-5">
      <PageTitle title={`${t}${d?.name ? ` — ${d.name}` : ''}`} sub={d ? `${d.exchange ?? '—'} · Ngành: ${d.sector ?? 'chưa phân ngành'} · Dữ liệu đến phiên ${dateVN(d.timeline.at(-1)?.date)}` : undefined} right={search} />
      {doc.loading ? <Loading /> : doc.error ? (
        doc.error instanceof NotFound ? <Empty title={`${t} chưa từng xuất hiện trong kết quả Exploration đã ghi nhận`} /> : <LoadError error={doc.error} />
      ) : d && (
        <>
          <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
            <Card title={`1–2. Vì sao xuất hiện & phương pháp nào đang nhận diện (phiên ${dateVN(meta.latest_session)})`}>
              {cur.length === 0 ? (
                <Empty title="Không đạt phương pháp nào trong phiên mới nhất">Xem lịch sử tín hiệu bên dưới.</Empty>
              ) : (
                <div className="space-y-3">
                  {cur.map((r) => {
                    const s = names[r.strategy_id]
                    return (
                      <div key={r.strategy_id} className="rounded-lg border border-line p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <StrategyChip id={r.strategy_id} />
                          <b>{s?.name}</b>
                          <StatusBadge s={r.signal_status} />
                          <span className="text-[12.5px] text-muted">Trạng thái: <b className="text-fg">{r.state ?? '—'}</b> · {s?.score_name}: <b className="text-fg">{num(r.strategy_score, 1)}</b> · Hạng {r.strategy_rank ?? '—'}{r.previous_rank !== null && ` (trước: ${r.previous_rank})`} · đạt {r.streak} phiên từ {dateVN(r.episode_start)}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-muted">
                          {s?.metrics.map((m) => {
                            const v = r.additional_metrics?.[m.key]
                            if (v === null || v === undefined) return null
                            return <span key={m.key}>{m.label}: <b className="num text-fg">{typeof v === 'number' ? num(v, Number.isInteger(v) ? 0 : 2) : typeof v === 'boolean' ? (v ? 'Có' : 'Không') : v}</b></span>
                          })}
                        </div>
                        <div className="mt-1 text-[12px] text-muted">{s?.description}</div>
                      </div>
                    )
                  })}
                  {cur[0] && (
                    <div className="flex flex-wrap gap-x-5 text-[12.5px] text-muted">
                      <span>Giá <b className="num text-fg">{price(cur[0].close)}</b></span>
                      <span>1P <b className={`num ${signClass(cur[0].ret_1d)}`}>{pct(cur[0].ret_1d)}</b></span>
                      <span>5P <b className={`num ${signClass(cur[0].ret_5d)}`}>{pct(cur[0].ret_5d)}</b></span>
                      <span>20P <b className={`num ${signClass(cur[0].ret_20d)}`}>{pct(cur[0].ret_20d)}</b></span>
                      <span>GTGD20 <b className="num text-fg">{bil(cur[0].avg_trading_value_20)}</b></span>
                    </div>
                  )}
                </div>
              )}
            </Card>
            <Card title="3. Lần đầu hay lặp lại?">
              <div className="overflow-auto">
              <table className="dt">
                <thead><tr><th>Phương pháp</th><th>Lần đầu</th><th>Gần nhất</th><th className="r">Số phiên</th><th className="r">Quay lại</th></tr></thead>
                <tbody>
                  {hrows.map((r) => (
                    <tr key={String(r[0])}>
                      <td><StrategyChip id={String(r[0])} /></td>
                      <td className="num">{dateVN(String(r[2]))}</td>
                      <td className="num">{dateVN(String(r[3]))}</td>
                      <td className="r num">{r[4]}</td>
                      <td className="r num">{r[6]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              {secRow && (
                <div className="mt-4 rounded-lg border border-line p-3 text-[12.5px]">
                  <div className="font-semibold">Ngành {secRow.sector}: hạng {secRow.rank ?? '—'}/{sectors.data!.rows.length} · {secRow.quadrant ?? '—'}</div>
                  <div className="mt-1 text-muted">RS-Z ngành {num(secRow.rsz, 2)} · RS-Mom {num(secRow.rsmom, 2)} · 20 phiên {pct(secRow.ret20)} (phiên {dateVN(sectors.data!.latest)})</div>
                </div>
              )}
            </Card>
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <Card title="4. Sức mạnh tương đối có cải thiện?">
              {rs.length < 2 ? <Empty title="Chưa đủ dữ liệu RS">RS chỉ được ghi ở các phiên mã có tín hiệu.</Empty> : (
                <>
                  <div className="mb-2 text-[12.5px] text-muted">RS (phân vị lợi suất 63 phiên toàn thị trường): hiện tại <b className="text-fg">{num(rsNow, 0)}</b>, so với ~20 phiên ghi nhận trước <b className={signClass(rsNow !== null && rs20 !== null ? rsNow - rs20 : null)}>{rsNow !== null && rs20 !== null ? `${rsNow - rs20 > 0 ? '+' : ''}${num(rsNow - rs20, 0)}` : '—'}</b></div>
                  <div className="h-52">
                    <ResponsiveContainer>
                      <LineChart data={rs.map(([date, v]) => ({ date, v }))}>
                        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                        <XAxis dataKey="date" tickFormatter={(x: string) => x.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={30} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--muted)' }} width={30} />
                        <Tooltip {...tip} labelFormatter={(x) => dateVN(String(x))} formatter={(v) => num(Number(v), 0)} />
                        <Line dataKey="v" name="RS" stroke="#34c38f" dot={false} strokeWidth={1.6} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-[12px] text-muted">Chỉ có điểm ở các phiên mã đạt ít nhất 1 phương pháp.</div>
                </>
              )}
            </Card>
            <Card title="Lịch sử hạng trong từng phương pháp">
              {rankSeries.length < 2 ? <Empty title="Chưa đủ dữ liệu" /> : (
                <div className="h-60">
                  <ResponsiveContainer>
                    <LineChart data={rankSeries}>
                      <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                      <XAxis dataKey="date" tickFormatter={(x: string) => x.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={30} />
                      <YAxis reversed tick={{ fontSize: 11, fill: 'var(--muted)' }} width={30} allowDecimals={false} />
                      <Tooltip {...tip} labelFormatter={(x) => dateVN(String(x))} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {usedStrats.map((s) => <Line key={s} dataKey={s} name={SHORT[s] ?? s} stroke={STRAT_COLORS[s]} dot={{ r: 1.5 }} strokeWidth={1.4} connectNulls={false} />)}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>
          <Card title="5. Các đợt tín hiệu đã ghi nhận và diễn biến sau đó">
            {d.episodes.length === 0 ? <Empty title="Chưa có đợt tín hiệu Mới/Quay lại nào" /> : (
              <div className="overflow-auto">
                <table className="dt">
                  <thead>
                    <tr>
                      <th>Ngày tín hiệu</th><th>Phương pháp</th><th>Loại</th><th className="r">Điểm</th><th>Nguồn</th>
                      {horizons.map((h) => <th key={h} className="r" title="Lợi suất gộp (vượt VN-Index)">{h} phiên</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {[...d.episodes].reverse().map((e) => (
                      <tr key={`${e.strategy_id}${e.start}`}>
                        <td className="num">{dateVN(e.start)}</td>
                        <td><StrategyChip id={e.strategy_id} /></td>
                        <td><StatusBadge s={e.status} /></td>
                        <td className="r num">{num(e.score, 1)}</td>
                        <td className="text-[12px] text-muted">{ORIGIN_LABEL[e.origin] ?? e.origin}</td>
                        {horizons.map((h) => {
                          const f = e.forward?.[h]
                          return <td key={h} className="r num">{f ? <><span className={signClass(f.gross)}>{pct(f.gross)}</span> <span className="text-muted">({pct(f.excess)})</span></> : <span className="text-muted">chờ</span>}</td>
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-2"><Note>Vào lệnh giả định ở giá mở cửa phiên kế tiếp sau ngày tín hiệu, thoát ở giá đóng cửa sau h phiên; số trong ngoặc là chênh lệch so với VN-Index cùng cửa sổ. “chờ” = chưa đủ số phiên. Không phải kết quả giao dịch thực tế.</Note></div>
          </Card>
        </>
      )}
    </div>
  )
}
