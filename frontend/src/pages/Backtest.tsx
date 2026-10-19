import type { PageProps } from '../App'
import { Card, Empty, Loading, Note, PageTitle, StrategyChip } from '../components/ui'
import { api, useLoad } from '../lib/data'
import { dateTimeVN, num } from '../lib/format'

const METRICS: { key: string; label: string; unit: string }[] = [
  { key: 'cagr', label: 'CAGR', unit: '%' },
  { key: 'max_drawdown', label: 'Max Drawdown', unit: '%' },
  { key: 'win_rate', label: 'Tỷ lệ thắng', unit: '%' },
  { key: 'profit_factor', label: 'Profit Factor', unit: '' },
  { key: 'sharpe', label: 'Sharpe', unit: '' },
  { key: 'avg_trade', label: 'Lãi/lỗ TB mỗi lệnh', unit: '%' },
  { key: 'avg_bars', label: 'Số phiên nắm giữ TB', unit: '' },
  { key: 'exposure', label: 'Exposure', unit: '%' },
  { key: 'trades', label: 'Số lệnh', unit: '' },
]

export default function Backtest(props: PageProps) {
  void props
  const bt = useLoad(() => api.backtest().catch(() => null), [])
  return (
    <div className="space-y-5">
      <PageTitle title="Backtest" sub="Kết quả backtest nhập từ báo cáo AmiBroker có nguồn rõ ràng — tách biệt với theo dõi tín hiệu hằng ngày." />
      {bt.loading ? <Loading /> : !bt.data || !bt.data.available || bt.data.reports.length === 0 ? (
        <Empty title="Đang chờ dữ liệu">
          Chưa có báo cáo backtest nào được nhập. Xuất danh sách lệnh từ AmiBroker (Backtest → Report → Trade list → Export) rồi chạy
          <code className="mx-1">python exporter\import_backtest.py --strategy VCP --file trades.csv</code>. Trang này không hiển thị số liệu tổng hợp hay mô phỏng.
        </Empty>
      ) : (
        <Card title="Báo cáo đã nhập">
          <div className="overflow-auto">
            <table className="dt">
              <thead>
                <tr>
                  <th>Phương pháp</th><th>Báo cáo</th><th>Giai đoạn</th>
                  {METRICS.map((m) => <th key={m.key} className="r">{m.label}</th>)}
                  <th>Nguồn</th>
                </tr>
              </thead>
              <tbody>
                {bt.data.reports.map((r) => (
                  <tr key={r.id}>
                    <td><StrategyChip id={r.strategy_id} /></td>
                    <td>{r.title}</td>
                    <td className="num">{r.period}</td>
                    {METRICS.map((m) => <td key={m.key} className="r num">{r.metrics[m.key] === null || r.metrics[m.key] === undefined ? '—' : `${num(r.metrics[m.key], 2)}${m.unit}`}</td>)}
                    <td className="text-[12px] text-muted" title={r.source}>{r.source.split(/[\\/]/).at(-1)} · {dateTimeVN(r.imported_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3"><Note>Chỉ số tính từ danh sách lệnh đã xuất (lợi suất mỗi lệnh theo % vốn của lệnh). Backtest là kết quả quá khứ trên dữ liệu đã điều chỉnh, không bảo đảm hiệu quả tương lai.</Note></div>
        </Card>
      )}
    </div>
  )
}
