import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PageProps } from '../App'
import { Card, Empty, LoadError, Loading, Note, PageTitle, SHORT, Stat, StrategyChip, TickerLink } from '../components/ui'
import { api, useLoad } from '../lib/data'
import { bil, dateTimeVN, dateVN, num, ORIGIN_LABEL, pct } from '../lib/format'
import { buildMulti } from '../lib/ranking'
import { href } from '../lib/router'

export const STRAT_COLORS: Record<string, string> = {
  VCP: '#34c38f', WYCKOFF: '#6aa2ff', PULLBACK: '#f2b84b', RS: '#c58af9', ROTATION: '#4dd0e1', HIGH_BETA: '#f0625a',
}

export default function Overview({ meta, status }: PageProps) {
  const summary = useLoad(() => api.summary(), [])
  const session = useLoad(() => (meta.latest_session ? api.session(meta.latest_session) : Promise.resolve(null)), [meta.latest_session])
  const trend = useLoad(() => api.signalTrend().catch(() => null), [])
  const breadth = useLoad(() => api.breadth().catch(() => null), [])
  if (summary.loading) return <Loading />
  if (summary.error) return <LoadError error={summary.error} />
  const L = summary.data?.latest
  const order = meta.strategies.map((s) => s.id)
  const multi = session.data ? buildMulti(session.data.records, order).filter((r) => r.n >= 2).slice(0, 12) : []
  const b = breadth.data?.series.at(-1)
  const trendData = (trend.data?.series ?? []).slice(-60)
  return (
    <div className="space-y-5">
      <PageTitle
        title="Tổng quan"
        sub="Hôm nay các phương pháp Exploration đang phát hiện cổ phiếu nào, tín hiệu nào mới, phương pháp nào đồng thuận và lịch sử tín hiệu ra sao."
      />
      {!L ? (
        <Empty title="Chưa có kết quả Exploration nào">Chạy exporter trên máy Windows (xem hướng dẫn trong README) để tạo dữ liệu.</Empty>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <Stat label="Phiên giao dịch" value={dateVN(L.session)} sub={`${L.strategies_available.length}/${meta.strategies.filter((s) => s.enabled).length} phương pháp có dữ liệu`} />
            <Stat label="Đồng bộ thành công" value={<span className="text-[15px]">{dateTimeVN(status?.last_success?.at ?? meta.built_at)}</span>} sub={status?.last_success ? ORIGIN_LABEL[status.last_success.kind] ?? status.last_success.kind : undefined} />
            <Stat label="Mã đạt ≥ 1 phương pháp" value={L.unique_tickers} tone="accent" />
            <Stat label="Tín hiệu mới" value={L.new + L.returning} sub={`${L.new} mới · ${L.returning} quay lại`} tone="pos" />
            <Stat label="Tiếp diễn" value={L.continuing} sub={L.unknown ? `${L.unknown} chưa so sánh được` : undefined} />
            <Stat label="Không còn đạt" value={L.dropped} sub="không phải tín hiệu bán" tone="warn" />
            <Stat label="Đạt ≥ 2 phương pháp" value={L.multi2} />
            <Stat label="Đạt ≥ 3 phương pháp" value={L.multi3} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
            <Card title="Kết quả theo phương pháp" right={<a className="text-[12.5px] text-accent" href={href('/exploration')}>Xem bảng chi tiết →</a>}>
              <div className="overflow-auto">
                <table className="dt">
                  <thead>
                    <tr>
                      <th>Phương pháp</th>
                      <th className="r">Đạt</th>
                      <th className="r">Mới</th>
                      <th className="r">Quay lại</th>
                      <th className="r">Tiếp diễn</th>
                      <th className="r">Không còn đạt</th>
                      <th>Nguồn</th>
                    </tr>
                  </thead>
                  <tbody>
                    {meta.strategies.map((s) => {
                      const x = L.by_strategy[s.id]
                      return (
                        <tr key={s.id}>
                          <td>
                            <a href={href('/exploration', { s: s.id })} className="font-medium hover:text-accent">{s.name}</a>
                            {!s.connected && <span className="tag ml-2 text-warn">Chưa kết nối</span>}
                          </td>
                          {x ? (
                            <>
                              <td className="r num">{x.total}</td>
                              <td className="r num text-pos">{x.new}</td>
                              <td className="r num text-info">{x.returning}</td>
                              <td className="r num">{x.continuing}</td>
                              <td className="r num text-warn">{x.dropped}</td>
                              <td className="text-[12px] text-muted">{ORIGIN_LABEL[x.origin] ?? x.origin}</td>
                            </>
                          ) : (
                            <td colSpan={6} className="text-[12px] text-muted">
                              Không có dữ liệu phiên này{s.last_session ? ` (gần nhất: ${dateVN(s.last_session)})` : ''}
                            </td>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="Đồng thuận nhiều phương pháp" right={<a className="text-[12.5px] text-accent" href={href('/ranking')}>Strategy Ranking →</a>}>
              {session.loading ? <Loading /> : multi.length === 0 ? (
                <Empty title="Không có mã nào đạt từ 2 phương pháp trong phiên này" />
              ) : (
                <table className="dt">
                  <thead>
                    <tr><th>Mã</th><th>Phương pháp</th><th className="r">GTGD20</th><th className="r">Chuỗi</th></tr>
                  </thead>
                  <tbody>
                    {multi.map((r) => (
                      <tr key={r.ticker}>
                        <td><TickerLink t={r.ticker} /></td>
                        <td><div className="flex flex-wrap gap-1">{r.strategies.map((s) => <StrategyChip key={s} id={s} />)}</div></td>
                        <td className="r num">{bil(r.avg_trading_value_20)}</td>
                        <td className="r num" title="Số phiên liên tiếp đạt ≥ 2 phương pháp">{r.multi_streak}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
            <Card title="Số mã đạt theo phiên">
              {trendData.length < 2 ? (
                <Empty title="Cần ít nhất 2 phiên để vẽ xu hướng" />
              ) : (
                <div className="h-64">
                  <ResponsiveContainer>
                    <BarChart data={trendData}>
                      <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                      <XAxis dataKey="session" tickFormatter={(d: string) => d.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={24} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--muted)' }} width={36} />
                      <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', fontSize: 12 }} labelFormatter={(d) => dateVN(String(d))} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {order.map((id) => (
                        <Bar key={id} dataKey={id} name={SHORT[id] ?? id} stackId="a" fill={STRAT_COLORS[id] ?? '#888'} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-2 text-[12px] text-muted">Phiên cũ có thể thiếu RS / High Beta vì hai phương pháp này chỉ tính được phiên cuối (không tái tạo lịch sử).</div>
            </Card>
            <Card title="Độ rộng thị trường" right={<a className="text-[12.5px] text-accent" href={href('/sectors')}>Thị trường & ngành →</a>}>
              {!b ? (
                <Empty title="Chưa có dữ liệu độ rộng">Cần dữ liệu giá toàn thị trường trên máy chạy exporter.</Empty>
              ) : (
                <div className="space-y-3">
                  <div className="text-[12.5px] text-muted">Phiên {dateVN(b.date)} · {b.ALL.n} mã có giao dịch (HOSE + HNX + UPCoM)</div>
                  {(['above_ma20', 'above_ma50', 'above_ma200'] as const).map((k) => (
                    <div key={k}>
                      <div className="flex justify-between text-[12.5px]"><span>% mã trên {k.replace('above_ma', 'MA')}</span><span className="num">{num(b.ALL[k], 1)}%</span></div>
                      <div className="mt-1 h-2 rounded bg-panel-2"><div className="h-2 rounded bg-accent" style={{ width: `${b.ALL[k] ?? 0}%` }} /></div>
                    </div>
                  ))}
                  <div className="flex gap-4 text-[12.5px]">
                    <span>Tăng <b className="text-pos">{b.ALL.advancers}</b></span>
                    <span>Giảm <b className="text-neg">{b.ALL.decliners}</b></span>
                    <span>Đỉnh 52 tuần <b>{b.ALL.new_high_52w}</b></span>
                  </div>
                  {session.data?.benchmark?.close !== undefined && (
                    <div className="text-[12.5px] text-muted">
                      VN-Index {num(session.data.benchmark.close, 2)} · 1 phiên {pct(session.data.benchmark.ret_1d ?? null, 2)} · 20 phiên {pct(session.data.benchmark.ret_20d ?? null, 1)}
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
          <Note>
            Trạng thái tín hiệu so với <b>phiên giao dịch có dữ liệu liền trước</b> của cùng phương pháp. “Không còn đạt” chỉ có nghĩa là mã không còn qua bộ lọc —
            không phải tín hiệu bán. Kết quả lọc theo quy tắc kỹ thuật, không phải khuyến nghị đầu tư.
          </Note>
        </>
      )}
    </div>
  )
}
