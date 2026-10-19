// Do "tuoi" du lieu theo LICH PHIEN (thu 2-6), gio Viet Nam. Khong biet ngay nghi le -> canh bao ghi ro "co the do nghi le".

/** Ngay + gio hien tai o Viet Nam (UTC+7, khong gio mua he). */
export function vnNow(now: Date = new Date()): { date: string; minutes: number; weekday: number } {
  const t = new Date(now.getTime() + 7 * 3600_000)
  const date = t.toISOString().slice(0, 10)
  return { date, minutes: t.getUTCHours() * 60 + t.getUTCMinutes(), weekday: t.getUTCDay() }
}

function addDays(iso: string, n: number): string {
  const t = new Date(`${iso}T00:00:00Z`)
  t.setUTCDate(t.getUTCDate() + n)
  return t.toISOString().slice(0, 10)
}

function weekday(iso: string): number {
  return new Date(`${iso}T00:00:00Z`).getUTCDay()
}

/** Phien gan nhat DA HOAN TAT ma du lieu nen co (chua tru nghi le).
 *  Ket qua EOD cua phien hom nay chi ky vong sau gio chot du lieu (mac dinh 18:30, sau lich cap nhat 18:00). */
export function expectedSession(now: Date = new Date(), readyMinutes = 18 * 60 + 30): string {
  const v = vnNow(now)
  let d = v.date
  if (!(v.weekday >= 1 && v.weekday <= 5 && v.minutes >= readyMinutes)) d = addDays(d, -1)
  while (weekday(d) === 0 || weekday(d) === 6) d = addDays(d, -1)
  return d
}

/** So phien (thu 2-6) tu `from` (khong tinh) den `to` (co tinh). */
export function weekdaysBetween(from: string, to: string): number {
  let n = 0
  let d = from
  while (d < to) {
    d = addDays(d, 1)
    const w = weekday(d)
    if (w !== 0 && w !== 6) n++
  }
  return n
}

export type Freshness = { level: 'fresh' | 'stale' | 'old' | 'none'; lag: number; expected: string }

export function freshness(latest: string | null | undefined, now: Date = new Date()): Freshness {
  const expected = expectedSession(now)
  if (!latest) return { level: 'none', lag: 0, expected }
  const lag = weekdaysBetween(latest, expected)
  return { level: lag === 0 ? 'fresh' : lag <= 2 ? 'stale' : 'old', lag, expected }
}
