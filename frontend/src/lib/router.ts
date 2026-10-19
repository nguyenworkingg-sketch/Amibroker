import { useEffect, useState } from 'react'

// Hash router toi gian (GitHub Pages khong ho tro rewrite duong dan): #/exploration?s=VCP&d=2026-10-16
export interface Route {
  path: string
  query: URLSearchParams
}

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#/, '') || '/'
  const [p, q = ''] = h.split('?')
  return { path: p.startsWith('/') ? p : `/${p}`, query: new URLSearchParams(q) }
}

export function href(path: string, query?: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) if (v !== null && v !== undefined && v !== '') q.set(k, String(v))
  const s = q.toString()
  return `#${path}${s ? `?${s}` : ''}`
}

export function navigate(path: string, query?: Record<string, string | number | null | undefined>, replace = false): void {
  const h = href(path, query)
  if (replace) history.replaceState(null, '', h)
  else location.hash = h
  if (replace) window.dispatchEvent(new HashChangeEvent('hashchange'))
}

export function useRoute(): Route {
  const [r, setR] = useState(() => parseHash(location.hash))
  useEffect(() => {
    const on = () => setR(parseHash(location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return r
}

/** Cap nhat 1 tham so query, giu nguyen cac tham so khac (khong tao muc lich su moi). */
export function setQuery(route: Route, patch: Record<string, string | number | null | undefined>): void {
  const q: Record<string, string> = {}
  route.query.forEach((v, k) => (q[k] = v))
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === undefined || v === '') delete q[k]
    else q[k] = String(v)
  }
  navigate(route.path, q, true)
}
