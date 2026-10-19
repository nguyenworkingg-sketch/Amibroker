import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, LabelList } from 'recharts'
import type { PageProps } from '../App'
import { DataTable, numCol, textCol } from '../components/DataTable'
import { Card, Empty, Loading, Note, PageTitle, Select, SHORT } from '../components/ui'
import { api, useLoad } from '../lib/data'
import { dateVN, num, pct, signClass } from '../lib/format'
import { href, type Route, setQuery } from '../lib/router'
import type { SectorRow } from '../lib/types'

type Universe = 'ALL' | 'HOSE' | 'HNX' | 'UPCoM'
const UNIV = [{ value: 'ALL', label: 'Toàn bộ (HOSE+HNX+UPCoM)' }, { value: 'HOSE', label: 'HOSE' }, { value: 'HNX', label: 'HNX' }, { value: 'UPCoM', label: 'UPCoM' }] as const
const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--border)', fontSize: 12 } }
const LINE_COLORS = ['#34c38f', '#6aa2ff', '#f2b84b', '#c58af9', '#f0625a', '#4dd0e1']

export default function Sectors({ meta, route }: PageProps & { route: Route }) {
  const u = (route.query.get('u') ?? 'ALL') as Universe
  const breadth = useLoad(() => api.breadth().catch(() => null), [])
  const sectors = useLoad(() => api.sectors().catch(() => null), [])
  const latest = useLoad(() => (meta.latest_session ? api.session(meta.latest_session) : Promise.resolve(null)), [meta.latest_session])
  const [picked, setPicked] = useState<string[]>([])

  const counts = useMemo(() => {
    const m = new Map<string, Record<string, number>>()
    for (const r of latest.data?.records ?? []) {
      if (!r.sector || (u !== 'ALL' && r.exchange !== u)) continue
      const x = m.get(r.sector) ?? {}
      x[r.strategy_id] = (x[r.strategy_id] ?? 0) + 1
      m.set(r.sector, x)
    }
    return m
  }, [latest.data, u])
  const rows: SectorRow[] = (sectors.data?.rows ?? []).map((r) => {
    const c = counts.get(r.sector) ?? {}
    return { ...r, signals: c, signals_total: Object.values(c).reduce((a, b) => a + b, 0) }
  })
  const top = rows.slice(0, 3).map((r) => r.sector)
  const show = picked.length ? picked : top
  const histData = useMemo(() => {
    const h = sectors.data?.history ?? {}
    const dates = new Set<string>()
    show.forEach((s) => (h[s] ?? []).forEach((p) => dates.add(p[0])))
    return [...dates].sort().map((d) => {
      const o: Record<string, string | number | null> = { date: d }
      show.forEach((s) => { const p = (h[s] ?? []).find((x) => x[0] === d); o[s] = p ? p[1] : null })
      return o
    })
  }, [sectors.data, show])
  const bser = (breadth.data?.series ?? []).map((b) => ({ date: b.date, ma20: b[u]?.above_ma20, ma50: b[u]?.above_ma50, ma200: b[u]?.above_ma200 }))
  const strategies = meta.strategies.map((s) => s.id)

  return (
    <div className="space-y-5">
      <PageTitle
        title="Thị trường & Ngành"
        sub="Độ rộng thị trường trên toàn bộ cổ phiếu (không chỉ mã đạt bộ lọc) và luân chuyển sức mạnh giữa các ngành."
        right={<Select label="Phạm vi" value={u} onChange={(v) => setQuery(route, { u: v === 'ALL' ? null : v })} options={[...UNIV]} />}
      />
      <Card title={`Độ rộng thị trường — ${UNIV.find((x) => x.value === u)?.label}`}>
        {breadth.loading ? <Loading /> : bser.length < 2 ? <Empty title="Chưa có dữ liệu độ rộng" /> : (
          <>
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={bser}>
                  <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={30} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--muted)' }} width={32} unit="%" />
                  <Tooltip {...tip} labelFormatter={(d) => dateVN(String(d))} formatter={(v) => `${num(Number(v), 1)}%`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <ReferenceLine y={50} stroke="var(--muted)" strokeDasharray="3 3" />
                  <Line dataKey="ma20" name="% trên MA20" stroke="#4dd0e1" dot={false} strokeWidth={1.5} />
                  <Line dataKey="ma50" name="% trên MA50" stroke="#34c38f" dot={false} strokeWidth={1.5} />
                  <Line dataKey="ma200" name="% trên MA200" stroke="#f2b84b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-1 text-[12px] text-muted">Mẫu số = mã có giao dịch trong phiên và đủ dữ liệu để tính đường trung bình. Phiên mới nhất: {bser.at(-1) && `${num(bser.at(-1)!.ma50 ?? null, 1)}% trên MA50`}.</div>
          </>
        )}
      </Card>

      {!sectors.data?.available ? (
        <Empty title="Chưa có bảng ngành">Exploration phụ trợ Hub_Sectors.afl (chỉ số NGANH_*) chưa chạy.</Empty>
      ) : (
        <>
          <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
            <Card title={`Bản đồ luân chuyển (RRG) — phiên ${dateVN(sectors.data.latest)}`}>
              <div className="h-80">
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                    <CartesianGrid stroke="var(--chart-grid)" />
                    <XAxis type="number" dataKey="rsz" name="RS-Z" tick={{ fontSize: 11, fill: 'var(--muted)' }} label={{ value: 'RS-Z so với VN-Index →', position: 'insideBottomRight', offset: -5, fontSize: 11, fill: 'var(--muted)' }} />
                    <YAxis type="number" dataKey="rsmom" name="RS-Mom" tick={{ fontSize: 11, fill: 'var(--muted)' }} width={36} label={{ value: 'RS-Mom ↑', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'var(--muted)' }} />
                    <ZAxis range={[60, 60]} />
                    <ReferenceLine x={0} stroke="var(--muted)" />
                    <ReferenceLine y={0} stroke="var(--muted)" />
                    <Tooltip {...tip} formatter={(v) => num(Number(v), 2)} />
                    <Scatter data={rows.filter((r) => r.rsz !== null && r.rsmom !== null)} fill="#34c38f">
                      <LabelList dataKey="sector" position="top" style={{ fontSize: 10, fill: 'var(--text)' }} />
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <div className="text-[12px] text-muted">Phải-trên: Dẫn dắt · Phải-dưới: Suy yếu · Trái-dưới: Tụt hậu · Trái-trên: Cải thiện. RS-Z / RS-Mom tính bằng PTKT_core trên chỉ số ngành NGANH_* (tự tính từ rổ cổ phiếu cố định hiện tại).</div>
            </Card>
            <Card title="Xu hướng RS-Z của ngành" right={<span className="text-[12px] text-muted">Bấm tên ngành trong bảng để chọn</span>}>
              <div className="h-80">
                <ResponsiveContainer>
                  <LineChart data={histData}>
                    <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={30} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--muted)' }} width={32} />
                    <ReferenceLine y={0} stroke="var(--muted)" />
                    <Tooltip {...tip} labelFormatter={(d) => dateVN(String(d))} formatter={(v) => num(Number(v), 2)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {show.map((s, i) => <Line key={s} dataKey={s} stroke={LINE_COLORS[i % LINE_COLORS.length]} dot={false} strokeWidth={1.6} connectNulls />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
          <Card title="Xếp hạng ngành">
            <DataTable<SectorRow>
              data={rows}
              rowKey={(r) => r.ticker}
              pageSize={50}
              initialSort={[{ id: 'rank', desc: true }]}
              columns={[
                numCol('rank', 'Hạng', (r) => (r.rank ? -r.rank : null), (_v, r) => r.rank ?? '—'),
                numCol('d1', 'Δ 1 phiên', (r) => (r.prev_rank && r.rank ? r.prev_rank - r.rank : null), (v) => <span className={signClass(v)}>{v === null || v === undefined ? '—' : v > 0 ? `▲${v}` : v < 0 ? `▼${-v}` : '0'}</span>),
                numCol('d5', 'Δ 5 phiên', (r) => (r.rank_5 && r.rank ? r.rank_5 - r.rank : null), (v) => <span className={signClass(v)}>{v === null || v === undefined ? '—' : v > 0 ? `▲${v}` : v < 0 ? `▼${-v}` : '0'}</span>),
                textCol('sector', 'Ngành', (r) => r.sector, (r) => (
                  <button className={`text-left hover:text-accent ${show.includes(r.sector) ? 'font-semibold text-accent' : ''}`}
                    onClick={() => setPicked((p) => (p.includes(r.sector) ? p.filter((x) => x !== r.sector) : [...(p.length ? p : []), r.sector].slice(-6)))}>
                    {r.sector}
                  </button>
                )),
                textCol('q', 'Góc RRG', (r) => r.quadrant),
                numCol('rsz', 'RS-Z', (r) => r.rsz, (v) => <span className={signClass(v)}>{num(v, 2)}</span>),
                numCol('rsm', 'RS-Mom', (r) => r.rsmom, (v) => <span className={signClass(v)}>{num(v, 2)}</span>),
                numCol('r5', '% 5P', (r) => r.ret5, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
                numCol('r20', '% 20P', (r) => r.ret20, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
                numCol('r60', '% 60P', (r) => r.ret60, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
                numCol('ex', 'Vượt VNI 3T', (r) => r.excess63, (v) => <span className={signClass(v)}>{pct(v, 1)}</span>),
                numCol('sig', 'Mã đạt', (r) => r.signals_total, (v) => num(v, 0), `Số tín hiệu (mã × phương pháp) phiên ${meta.latest_session} trong phạm vi đã chọn`),
                textCol('by', 'Theo phương pháp', () => null, (r) => (
                  <div className="flex flex-wrap gap-1">
                    {strategies.filter((s) => r.signals[s]).map((s) => (
                      <a key={s} className="tag hover:border-accent" href={href('/exploration', { s, sec: r.sector })}>{SHORT[s]} <span className="num ml-1">{r.signals[s]}</span></a>
                    ))}
                  </div>
                )),
              ]}
            />
            <div className="mt-2"><Note>Chỉ 19 nhóm ngành PTKT (~230 mã) có phân ngành; mã ngoài danh sách hiển thị “—” ở cột Ngành. Danh sách thành viên ngành là danh sách hiện tại, nên lịch sử ngành có thiên lệch sống sót.</Note></div>
          </Card>
        </>
      )}
    </div>
  )
}
