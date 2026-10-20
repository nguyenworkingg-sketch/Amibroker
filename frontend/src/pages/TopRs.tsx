import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PageProps } from '../App'
import { DataTable, numCol, textCol } from '../components/DataTable'
import { Card, Empty, LoadError, Loading, Note, PageTitle, Select, Stat, TickerLink } from '../components/ui'
import { downloadCsv, toCsv } from '../lib/csv'
import { api, useLoad } from '../lib/data'
import { bil, dateVN, num, pct, price, signClass } from '../lib/format'
import { type Route, setQuery } from '../lib/router'
import type { TopRsRow } from '../lib/types'

const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--border)', fontSize: 12 } }

function smCell(v: number | null | undefined) {
  if (v === null || v === undefined) return '—'
  const c = v >= 90 ? 'text-pos font-semibold' : v >= 80 ? 'text-pos' : v < 50 ? 'text-neg' : ''
  return <span className={c}>{num(v, 0)}</span>
}

const retCell = (v: number | null | undefined) => <span className={signClass(v)}>{pct(v, 2)}</span>

export default function TopRs({ route }: PageProps & { route: Route }) {
  const doc = useLoad(() => api.topRs(), [])
  const tab = route.query.get('tab') ?? 'top'
  const ex = route.query.get('ex') ?? 'ALL'
  const sec = route.query.get('sec') ?? 'ALL'
  const fresh = Number(route.query.get('moi') ?? 0)
  const [q, setQ] = useState('')
  const set = (p: Record<string, string | number | null>) => setQuery(route, p)

  const d = doc.data
  const base = useMemo(() => (tab === 'exit' ? d?.recent_exits : d?.rows) ?? [], [d, tab])
  const rows = useMemo(
    () => base.filter((r) => (ex === 'ALL' || r.exchange === ex) && (sec === 'ALL' || r.sector === sec) && (!q || r.ticker.includes(q.toUpperCase()))
      && (tab === 'exit' || !fresh || (r.sessions <= fresh && !r.entry_censored))),
    [base, ex, sec, q, fresh, tab],
  )
  const sectors = useMemo(() => [...new Set(base.map((r) => r.sector).filter((s): s is string => !!s))].sort((a, b) => a.localeCompare(b, 'vi')), [base])

  if (doc.loading) return <Loading />
  if (doc.error) return <LoadError error={doc.error} />
  if (!d?.available || !d.summary || !d.rule) return <Empty title="Chưa có dữ liệu Top RS">Cần chuỗi giá từ AmiBroker trên máy chạy exporter.</Empty>
  const s = d.summary
  const rule = d.rule

  const cols: ColumnDef<TopRsRow, unknown>[] = [
    {
      id: 'stt', header: 'STT', enableSorting: false, meta: { align: 'right' },
      // so thu tu theo dung thu tu dang hien thi (sau khi sap xep)
      cell: ({ row, table }) => table.getSortedRowModel().rows.findIndex((x) => x.id === row.id) + 1,
    },
    textCol<TopRsRow>('ticker', 'Mã CP', (r) => r.ticker, (r) => (
      <span className="flex items-center gap-1.5"><TickerLink t={r.ticker} />{r.new_today && <span className="tag border-accent text-accent">Mới</span>}</span>
    )),
    textCol<TopRsRow>('sector', 'Tên ngành', (r) => r.sector, (r) => <span title={r.sector_l3 ?? ''}>{r.sector ?? '—'}</span>),
    textCol<TopRsRow>('exchange', 'Sàn', (r) => r.exchange),
    textCol<TopRsRow>('entry', 'Ngày vào top', (r) => r.entry_date, (r) => (
      <span className="num" title={r.entry_censored ? `Đã ở top từ trước ngày bắt đầu theo dõi (${dateVN(d.tracking_since)})` : ''}>
        {r.entry_censored ? '≤ ' : ''}{dateVN(r.entry_date)}
      </span>
    )),
    ...(tab === 'exit' ? [textCol<TopRsRow>('exitd', 'Ngày rời top', (r) => r.exit_date, (r) => <span className="num">{dateVN(r.exit_date)}</span>)] : []),
    numCol<TopRsRow>('sessions', tab === 'exit' ? 'Số phiên ở top' : 'Số phiên top', (r) => r.sessions, (v) => num(v, 0), 'Số phiên giao dịch kể cả phiên vào top'),
    ...(tab === 'exit'
      ? [numCol<TopRsRow>('smx', 'SM khi rời', (r) => r.sm_mid_exit, smCell),
         textCol<TopRsRow>('why', 'Lý do rời', (r) => r.exit_reason, (r) => (r.exit_reason === 'illiquid' ? 'Rời rổ thanh khoản (> 10 phiên không xếp hạng)' : `SM trung hạn < ${rule.exit}`))]
      : [
          numCol<TopRsRow>('sms', 'SM ngắn hạn', (r) => r.sm_short, smCell, `Hạng lợi suất vượt VN-Index ${rule.short_sessions} phiên trong rổ (1–99)`),
          numCol<TopRsRow>('smm', 'SM trung hạn', (r) => r.sm_mid, smCell, 'RS Rating 1–99 (trọng số 3–6–9–12 tháng so với VN-Index)'),
        ]),
    numCol<TopRsRow>('p0', 'Giá vào top', (r) => r.entry_price, (v) => price(v)),
    numCol<TopRsRow>('p1', tab === 'exit' ? 'Giá khi rời' : 'Giá hiện tại', (r) => r.price, (v) => price(v)),
    numCol<TopRsRow>('ret', 'Tăng/giảm', (r) => r.ret_pct, retCell),
    numCol<TopRsRow>('vni', 'VN-Index cùng kỳ', (r) => r.vni_ret_pct, retCell),
    numCol<TopRsRow>('exc', 'Vượt VN-Index', (r) => r.excess_pct, retCell, 'Tăng/giảm của mã trừ VN-Index cùng kỳ (điểm %)'),
    numCol<TopRsRow>('max', 'Cao nhất từ khi vào', (r) => r.max_ret_pct, retCell, 'Mức lãi cao nhất (theo giá đóng cửa) kể từ ngày vào top'),
    ...(tab === 'exit' ? [] : [numCol<TopRsRow>('liq', 'GTGD20', (r) => r.avg_trading_value_20, (v) => bil(v))]),
  ]

  return (
    <div className="space-y-4">
      <PageTitle
        title="Top RS"
        sub={`Cổ phiếu trong nhóm sức mạnh tương đối cao nhất toàn thị trường — phiên ${dateVN(d.session)}`}
        right={<span className="text-[12px] text-muted">Theo dõi từ {dateVN(d.tracking_since)}</span>}
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Đang trong top" value={s.in_top} sub={`rổ ${s.universe} mã GTGD20 ≥ ${num(rule.min_value_bil, 0)} tỷ`} tone="accent" />
        <Stat label="Mới vào hôm nay" value={s.new_today} tone="pos" />
        <Stat label="Rời top hôm nay" value={s.exits_today} tone="warn" />
        <Stat label="Đang lãi từ khi vào" value={s.pct_positive === null ? '—' : `${num(s.pct_positive, 0)}%`} sub={`${s.measured} mã có ngày vào thật`} />
        <Stat label="Lợi suất trung vị" value={pct(s.median_ret_pct, 1)} sub={`trung bình ${pct(s.avg_ret_pct, 1)}`} tone={s.median_ret_pct !== null && s.median_ret_pct < 0 ? 'neg' : 'pos'} />
        <Stat label="Vượt VN-Index (TB)" value={pct(s.avg_excess_pct, 1)} tone={s.avg_excess_pct !== null && s.avg_excess_pct < 0 ? 'neg' : 'pos'} />
      </div>
      <Note>
        <b>Quy tắc:</b> vào top khi <b>SM trung hạn (RS Rating) ≥ {rule.enter}</b> (~ top {100 - rule.enter}% rổ); chỉ rời top khi <b>&lt; {rule.exit}</b> (vùng đệm
        để không ra/vào liên tục). Rổ mỗi phiên: mã HOSE/HNX/UPCoM có giao dịch và GTGD20 ≥ {num(rule.min_value_bil, 0)} tỷ. RS Rating cùng công thức bảng Xếp hạng
        trong AmiBroker. Giá đã điều chỉnh (cổ tức/quyền). Mã ghi “≤ ngày” đã ở top từ trước ngày bắt đầu theo dõi và không tính vào tổng kết.
        Danh sách theo dõi sức mạnh giá, không phải khuyến nghị mua bán.
      </Note>
      <Card>
        <div className="mb-3 flex flex-wrap gap-1.5" role="tablist">
          <button role="tab" aria-selected={tab === 'top'} className={`btn ${tab === 'top' ? 'on' : ''}`} onClick={() => set({ tab: null })}>
            Đang trong top <span className="num text-muted">{d.rows?.length ?? 0}</span>
          </button>
          <button role="tab" aria-selected={tab === 'exit'} className={`btn ${tab === 'exit' ? 'on' : ''}`} onClick={() => set({ tab: 'exit' })}>
            Rời top 20 phiên gần đây <span className="num text-muted">{d.recent_exits?.length ?? 0}</span>
          </button>
        </div>
        <DataTable<TopRsRow>
          key={tab}
          data={rows}
          columns={cols}
          rowKey={(r) => `${r.ticker}:${r.entry_date}`}
          initialSort={[{ id: tab === 'exit' ? 'exitd' : 'entry', desc: true }]}
          pageSize={100}
          toolbar={
            <>
              <input className="inp w-32" placeholder="Tìm mã…" value={q} onChange={(e) => setQ(e.target.value)} />
              <Select label="Sàn" value={ex} onChange={(v) => set({ ex: v === 'ALL' ? null : v })}
                options={[{ value: 'ALL', label: 'Tất cả' }, { value: 'HOSE', label: 'HOSE' }, { value: 'HNX', label: 'HNX' }, { value: 'UPCoM', label: 'UPCoM' }]} />
              <Select label="Ngành" value={sec} onChange={(v) => set({ sec: v === 'ALL' ? null : v })}
                options={[{ value: 'ALL', label: 'Tất cả' }, ...sectors.map((x) => ({ value: x, label: x }))]} />
              {tab !== 'exit' && (
                <Select label="Mới vào trong" value={String(fresh)} onChange={(v) => set({ moi: v === '0' ? null : v })}
                  options={[{ value: '0', label: 'Tất cả' }, { value: '1', label: 'hôm nay' }, { value: '5', label: '5 phiên' }, { value: '10', label: '10 phiên' }, { value: '20', label: '20 phiên' }]} />
              )}
              <button className="btn" onClick={() => downloadCsv(`top_rs_${tab}_${d.session}.csv`, toCsv(rows, [
                { header: 'Ma', value: (r) => r.ticker }, { header: 'Nganh', value: (r) => r.sector }, { header: 'San', value: (r) => r.exchange },
                { header: 'NgayVaoTop', value: (r) => (r.entry_censored ? `<=${r.entry_date}` : r.entry_date) }, { header: 'NgayRoiTop', value: (r) => r.exit_date },
                { header: 'SoPhien', value: (r) => r.sessions }, { header: 'SMNganHan', value: (r) => r.sm_short }, { header: 'SMTrungHan', value: (r) => r.sm_mid },
                { header: 'GiaVaoTop', value: (r) => r.entry_price }, { header: 'GiaHienTai', value: (r) => r.price }, { header: 'TangGiamPct', value: (r) => r.ret_pct },
                { header: 'VNIndexPct', value: (r) => r.vni_ret_pct }, { header: 'VuotVNIPct', value: (r) => r.excess_pct }, { header: 'CaoNhatPct', value: (r) => r.max_ret_pct },
              ]))}>Tải CSV</button>
            </>
          }
        />
      </Card>
      {d.series && d.series.length > 1 && (
        <Card title="Số mã trong top theo phiên">
          <div className="h-56">
            <ResponsiveContainer>
              <ComposedChart data={d.series}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(x: string) => x.slice(5).split('-').reverse().join('/')} tick={{ fontSize: 11, fill: 'var(--muted)' }} minTickGap={30} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--muted)' }} width={32} />
                <Tooltip {...tip} labelFormatter={(x) => dateVN(String(x))} />
                <Bar dataKey="new" name="Mới vào" fill="#34c38f" isAnimationActive={false} />
                <Bar dataKey="exits" name="Rời top" fill="#f2b84b" isAnimationActive={false} />
                <Line dataKey="in_top" name="Đang trong top" stroke="#6aa2ff" dot={false} strokeWidth={1.6} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  )
}
