// Dinh dang so kieu Viet Nam: dau phay thap phan, dau cham phan nghin. null -> "—" (khong bao gio hien 0 gia).
const cacheFmt = new Map<string, Intl.NumberFormat>()
function nf(min: number, max: number): Intl.NumberFormat {
  const k = `${min}-${max}`
  let f = cacheFmt.get(k)
  if (!f) {
    f = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: min, maximumFractionDigits: max })
    cacheFmt.set(k, f)
  }
  return f
}

export const DASH = '—'

export function num(v: number | null | undefined, digits = 2, minDigits = digits): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH
  return nf(minDigits, digits).format(v)
}

export function pct(v: number | null | undefined, digits = 1, sign = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH
  const s = nf(digits, digits).format(v)
  return `${sign && v > 0 ? '+' : ''}${s}%`
}

/** Gia: nghin dong (vd 58,20) */
export function price(v: number | null | undefined): string {
  return num(v, 2, 2)
}

/** Gia tri giao dich: ty dong */
export function bil(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH
  return `${num(v, v >= 100 ? 0 : 1, v >= 100 ? 0 : 1)} tỷ`
}

export function signClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return ''
  return v > 0 ? 'text-pos' : 'text-neg'
}

export function dateVN(iso: string | null | undefined): string {
  if (!iso) return DASH
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

export function dateTimeVN(iso: string | null | undefined): string {
  if (!iso) return DASH
  const t = new Date(iso)
  if (Number.isNaN(t.getTime())) return iso
  return t.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' })
}

export const STATUS_LABEL: Record<string, string> = {
  NEW: 'Mới',
  RETURNING: 'Quay lại',
  CONTINUING: 'Tiếp diễn',
  DROPPED: 'Không còn đạt',
  UNKNOWN: 'Chưa so sánh',
}

export const ORIGIN_LABEL: Record<string, string> = {
  live: 'Chạy thật',
  backfill: 'Tái tạo lịch sử',
  manual: 'Nhập tay',
  demo: 'Mô phỏng',
}
