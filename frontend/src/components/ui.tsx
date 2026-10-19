import type { ReactNode } from 'react'
import { NotFound } from '../lib/data'
import { STATUS_LABEL } from '../lib/format'
import { href } from '../lib/router'

export function Card({ title, right, children, className = '' }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-[13.5px] font-semibold">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'pos' | 'neg' | 'warn' | 'accent' }) {
  const c = tone === 'pos' ? 'text-pos' : tone === 'neg' ? 'text-neg' : tone === 'warn' ? 'text-warn' : tone === 'accent' ? 'text-accent' : ''
  return (
    <div className="card px-4 py-3">
      <div className="text-[12px] text-muted">{label}</div>
      <div className={`mt-1 break-words text-[clamp(16px,1.6vw,22px)] font-semibold leading-tight ${c}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11.5px] text-muted">{sub}</div>}
    </div>
  )
}

const STATUS_STYLE: Record<string, string> = {
  NEW: 'border-accent text-accent',
  RETURNING: 'border-info text-info',
  CONTINUING: 'text-muted',
  DROPPED: 'border-warn text-warn',
  UNKNOWN: 'text-muted border-dashed',
}

export function StatusBadge({ s }: { s: string }) {
  return <span className={`tag ${STATUS_STYLE[s] ?? ''}`}>{STATUS_LABEL[s] ?? s}</span>
}

export function StrategyChip({ id, short = true }: { id: string; short?: boolean }) {
  return (
    <a href={href('/exploration', { s: id })} className="tag hover:border-accent" title={id}>
      {short ? SHORT[id] ?? id : id}
    </a>
  )
}

export const SHORT: Record<string, string> = {
  VCP: 'VCP', WYCKOFF: 'Wyckoff', PULLBACK: 'Pullback', RS: 'RS', ROTATION: 'Rotation', HIGH_BETA: 'High Beta',
}

export function TickerLink({ t }: { t: string }) {
  return (
    <a href={href('/stock', { t })} className="font-semibold text-accent hover:underline">
      {t}
    </a>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-6 py-10 text-center">
      <div className="font-semibold">{title}</div>
      {children && <div className="mx-auto mt-2 max-w-xl text-[13px] text-muted">{children}</div>}
    </div>
  )
}

export function Loading() {
  return <div className="py-10 text-center text-muted">Đang tải dữ liệu…</div>
}

export function LoadError({ error }: { error: Error }) {
  if (error instanceof NotFound)
    return <Empty title="Chưa có dữ liệu">Tệp dữ liệu <code>{error.message}</code> chưa được tạo. Hệ thống sẽ hiển thị khi exporter chạy xong.</Empty>
  return <Empty title="Không tải được dữ liệu">{error.message}</Empty>
}

export function PageTitle({ title, sub, right }: { title: string; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[20px] font-semibold">{title}</h1>
        {sub && <div className="mt-0.5 text-[13px] text-muted">{sub}</div>}
      </div>
      {right}
    </div>
  )
}

export function Note({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'warn' }) {
  return (
    <div className={`rounded-lg border px-3 py-2 text-[12.5px] ${tone === 'warn' ? 'border-warn bg-warn-soft text-fg' : 'border-line text-muted'}`}>{children}</div>
  )
}

export function Select<T extends string>({ value, onChange, options, label }: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  label: string
}) {
  return (
    <label className="flex items-center gap-1.5 text-[12.5px] text-muted">
      {label}
      <select className="inp" value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}
