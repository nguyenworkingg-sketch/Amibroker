import type { PageProps } from '../App'
import { FreshnessBanner } from '../App'
import { Card, Empty, Note, PageTitle, Stat, StrategyChip } from '../components/ui'
import { dateTimeVN, dateVN, num, ORIGIN_LABEL } from '../lib/format'
import { freshness } from '../lib/freshness'

const RESULT: Record<string, { label: string; cls: string }> = {
  success: { label: 'Thành công', cls: 'text-pos' },
  partial: { label: 'Một phần', cls: 'text-warn' },
  failed: { label: 'Thất bại', cls: 'text-neg' },
  skipped: { label: 'Hoãn', cls: 'text-warn' },
  running: { label: 'Đang chạy', cls: 'text-info' },
}
const STEP: Record<string, string> = {
  created: 'Đã ghi', unchanged: 'Không đổi', replaced: 'Cập nhật', invalid: 'File không hợp lệ', error: 'Lỗi', timeout: 'Quá thời gian',
  empty_suspicious: 'Rỗng bất thường — giữ dữ liệu cũ', ok: 'OK', skipped: 'Bỏ qua',
}

export default function Status({ meta, status }: PageProps) {
  const f = freshness(meta.latest_session)
  const enabled = meta.strategies.filter((s) => s.enabled)
  const missing = enabled.filter((s) => s.last_session !== meta.latest_session)
  return (
    <div className="space-y-5">
      <PageTitle title="System Status" sub="Tình trạng đồng bộ AmiBroker → exporter → GitHub → website." />
      <FreshnessBanner meta={meta} status={status} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Phiên dữ liệu mới nhất" value={dateVN(meta.latest_session)} sub={f.level === 'fresh' ? 'đúng phiên dự kiến' : `dự kiến ${dateVN(f.expected)}`} tone={f.level === 'fresh' ? 'pos' : 'warn'} />
        <Stat label="Đồng bộ thành công gần nhất" value={<span className="text-[15px]">{dateTimeVN(status?.last_success?.at)}</span>} sub={status?.last_success ? ORIGIN_LABEL[status.last_success.kind] ?? status.last_success.kind : 'chưa có'} />
        <Stat label="Lần chạy gần nhất" value={<span className={`text-[15px] ${RESULT[status?.last_run?.result ?? '']?.cls ?? ''}`}>{RESULT[status?.last_run?.result ?? '']?.label ?? '—'}</span>} sub={dateTimeVN(status?.last_run?.finished_at)} />
        <Stat label="Xuất bản lên web" value={<span className="text-[15px]">{dateTimeVN(status?.last_publication?.at ?? meta.built_at)}</span>} sub="thời điểm đẩy dữ liệu lên GitHub" />
        <Stat label="Số phiên lưu trữ" value={meta.sessions.length} />
        <Stat label="Nguồn thiếu / cũ" value={missing.length} tone={missing.length ? 'warn' : 'pos'} sub={missing.map((s) => s.id).join(', ') || 'đủ'} />
      </div>
      <Card title="Trạng thái từng phương pháp">
        <div className="overflow-auto">
          <table className="dt">
            <thead>
              <tr><th>Phương pháp</th><th>Kết nối</th><th>Phiên gần nhất</th><th className="r">Số mã</th><th>Lần chạy gần nhất</th><th>Kết quả</th><th>Ghi chú</th><th>Lịch sử từ</th><th>AFL adapter</th></tr>
            </thead>
            <tbody>
              {meta.strategies.map((s) => {
                const st = status?.strategies?.[s.id]
                return (
                  <tr key={s.id}>
                    <td><StrategyChip id={s.id} /> <span className="text-[12px] text-muted">v{s.version}</span></td>
                    <td>{!s.enabled ? <span className="text-muted">Tắt</span> : s.connected ? <span className="text-pos">Đã kết nối</span> : <span className="text-warn">Chưa kết nối</span>}</td>
                    <td className={`num ${s.last_session !== meta.latest_session ? 'text-warn' : ''}`}>{dateVN(s.last_session)}</td>
                    <td className="r num">{num(s.last_count, 0)}</td>
                    <td className="num">{dateTimeVN(st?.last_run_at)}</td>
                    <td>{st?.last_status ? STEP[st.last_status] ?? st.last_status : '—'}</td>
                    <td className="max-w-96 truncate text-[12px] text-muted" title={st?.last_error ?? st?.last_message ?? ''}>{st?.last_error ?? st?.last_message ?? ''}</td>
                    <td className="num">{dateVN(s.first_session)}</td>
                    <td className="text-[12px] text-muted">{s.adapter_afl}{s.two_pass ? ' (Scan + Explore)' : ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Nhật ký chạy (60 lần gần nhất)">
        {!status?.runs?.length ? <Empty title="Chưa có lần chạy nào được ghi" /> : (
          <div className="space-y-2">
            {status.runs.map((r) => (
              <details key={r.run_id} className="rounded-lg border border-line px-3 py-2">
                <summary className="cursor-pointer text-[13px]">
                  <span className={`font-semibold ${RESULT[r.result]?.cls ?? ''}`}>{RESULT[r.result]?.label ?? r.result}</span>
                  <span className="ml-2 text-muted">{dateTimeVN(r.started_at)} · {ORIGIN_LABEL[r.kind] ?? r.kind} · phiên {dateVN(r.session)} · {r.message}</span>
                </summary>
                <table className="dt mt-2">
                  <thead><tr><th>Bước</th><th>Kết quả</th><th>Phiên</th><th className="r">Số mã</th><th className="r">Giây</th><th>Chi tiết</th></tr></thead>
                  <tbody>
                    {r.steps.map((s, i) => (
                      <tr key={i}>
                        <td>{s.name}</td>
                        <td>{STEP[s.status] ?? s.status}</td>
                        <td className="num">{s.session ?? ''}</td>
                        <td className="r num">{s.records ?? ''}</td>
                        <td className="r num">{s.seconds ?? ''}</td>
                        <td className="max-w-[40rem] whitespace-normal text-[12px] text-muted">{s.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            ))}
          </div>
        )}
      </Card>
      <Note>
        Website là trang tĩnh (GitHub Pages), chỉ đọc file JSON đã xuất — không kết nối trực tiếp tới AmiBroker. Khi máy Windows tắt hoặc lỗi, trang
        tiếp tục hiển thị lần đồng bộ thành công gần nhất kèm cảnh báo dữ liệu cũ. Exporter không bao giờ ghi đè dữ liệu hợp lệ bằng kết quả rỗng hoặc lỗi.
      </Note>
    </div>
  )
}
