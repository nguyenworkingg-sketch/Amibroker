import { lazy, Suspense, useEffect, useState } from 'react'
import { LoadError, Loading } from './components/ui'
import { api, useLoad } from './lib/data'
import { dateTimeVN, dateVN } from './lib/format'
import { freshness } from './lib/freshness'
import { href, useRoute } from './lib/router'
import type { Meta, StatusDoc } from './lib/types'
import Exploration from './pages/Exploration'
import Ranking from './pages/Ranking'

// Trang co bieu do (Recharts) tai khi can de trang Exploration mo nhanh
const Overview = lazy(() => import('./pages/Overview'))
const History = lazy(() => import('./pages/History'))
const Sectors = lazy(() => import('./pages/Sectors'))
const Stock = lazy(() => import('./pages/Stock'))
const Backtest = lazy(() => import('./pages/Backtest'))
const Status = lazy(() => import('./pages/Status'))

const NAV = [
  { path: '/', label: 'Tổng quan' },
  { path: '/exploration', label: 'Daily Exploration' },
  { path: '/ranking', label: 'Strategy Ranking' },
  { path: '/history', label: 'Signal History' },
  { path: '/sectors', label: 'Sector Rotation' },
  { path: '/stock', label: 'Stock Detail' },
  { path: '/backtest', label: 'Backtest' },
  { path: '/status', label: 'System Status' },
]

export interface PageProps {
  meta: Meta
  status: StatusDoc | null
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem('hub-theme', dark ? 'dark' : 'light')
    } catch {
      /* trinh duyet chan luu tru -> bo qua */
    }
  }, [dark])
  return (
    <button className="btn" onClick={() => setDark((d) => !d)} title="Đổi giao diện sáng/tối">
      {dark ? '☀ Sáng' : '☾ Tối'}
    </button>
  )
}

export function FreshnessBanner({ meta, status }: PageProps) {
  const f = freshness(meta.latest_session)
  if (f.level === 'fresh') return null
  const lastRun = status?.last_run
  return (
    <div className="mb-4 rounded-lg border border-warn bg-warn-soft px-4 py-2.5 text-[13px]">
      <b>{f.level === 'none' ? 'Chưa có dữ liệu Exploration.' : `Dữ liệu cũ: phiên mới nhất là ${dateVN(meta.latest_session)}`}</b>
      {f.level !== 'none' && (
        <> — chậm {f.lag} phiên so với phiên dự kiến {dateVN(f.expected)} (có thể do nghỉ lễ, hoặc máy Windows chạy AmiBroker chưa xuất dữ liệu). </>
      )}
      Trang đang hiển thị lần đồng bộ thành công gần nhất.
      {lastRun && lastRun.result !== 'success' && (
        <> Lần chạy gần nhất ({dateTimeVN(lastRun.finished_at)}): <b>{lastRun.result}</b> — {lastRun.message}</>
      )}
    </div>
  )
}

export default function App() {
  const route = useRoute()
  const meta = useLoad(() => api.meta(), [])
  const status = useLoad(() => api.status().catch(() => null), [])
  const [navOpen, setNavOpen] = useState(false)
  useEffect(() => setNavOpen(false), [route.path])

  let body
  if (meta.loading) body = <Loading />
  else if (meta.error || !meta.data) body = <LoadError error={meta.error ?? new Error('Không có meta.json')} />
  else {
    const p: PageProps = { meta: meta.data, status: status.data ?? null }
    const page =
      {
        '/': <Overview {...p} />,
        '/exploration': <Exploration {...p} route={route} />,
        '/ranking': <Ranking {...p} route={route} />,
        '/history': <History {...p} route={route} />,
        '/sectors': <Sectors {...p} route={route} />,
        '/stock': <Stock {...p} route={route} />,
        '/backtest': <Backtest {...p} />,
        '/status': <Status {...p} />,
      }[route.path] ?? <Overview {...p} />
    body = (
      <>
        {meta.data.demo && (
          <div className="mb-4 rounded-lg border border-info px-4 py-2 text-[13px] text-info">
            <b>Dữ liệu mô phỏng</b> — các con số trên trang này là dữ liệu minh họa, không phải kết quả Exploration thật.
          </div>
        )}
        {route.path !== '/status' && <FreshnessBanner {...p} />}
        <Suspense fallback={<Loading />}>{page}</Suspense>
      </>
    )
  }
  const m = meta.data
  return (
    <div className="flex min-h-full">
      <aside className={`${navOpen ? 'block' : 'hidden'} fixed inset-y-0 left-0 z-30 w-56 shrink-0 border-r border-line bg-panel lg:sticky lg:top-0 lg:block lg:h-screen`}>
        <div className="px-4 py-4">
          <a href="#/" className="block">
            <div className="text-[15px] font-bold leading-tight">AmiBroker</div>
            <div className="text-[12px] font-medium text-accent">Exploration Hub</div>
          </a>
        </div>
        <nav className="px-2">
          {NAV.map((n) => {
            const on = route.path === n.path
            return (
              <a key={n.path} href={href(n.path)} className={`block rounded-md px-3 py-1.5 text-[13.5px] ${on ? 'bg-accent-soft font-semibold text-fg' : 'text-muted hover:bg-panel-2 hover:text-fg'}`}>
                {n.label}
              </a>
            )
          })}
        </nav>
        <div className="absolute bottom-0 w-full border-t border-line px-4 py-3 text-[11.5px] text-muted">
          Kết quả lọc theo quy tắc kỹ thuật, <b>không phải khuyến nghị đầu tư</b>.
        </div>
      </aside>
      {navOpen && <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={() => setNavOpen(false)} />}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-bg/90 px-4 py-2.5 backdrop-blur">
          <div className="flex items-center gap-3">
            <button className="btn lg:hidden" onClick={() => setNavOpen(true)} aria-label="Mở menu">
              ☰
            </button>
            {m && (
              <div className="text-[12.5px] text-muted">
                Phiên: <b className="text-fg">{dateVN(m.latest_session)}</b>
                <span className="hidden sm:inline">
                  {' '}· Đồng bộ: {dateTimeVN(status.data?.last_success?.at ?? m.built_at)}
                </span>
              </div>
            )}
          </div>
          <ThemeToggle />
        </header>
        <main className="mx-auto max-w-[1500px] px-4 py-5">{body}</main>
      </div>
    </div>
  )
}
