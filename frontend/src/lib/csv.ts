export interface CsvColumn<T> {
  header: string
  value: (row: T) => string | number | boolean | null | undefined
}

function cell(v: string | number | boolean | null | undefined): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  return /[",\n\r;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** CSV UTF-8 co BOM (Excel doc dung tieng Viet), dau phay phan cach, so dung dau cham thap phan, o trong = thieu du lieu. */
export function toCsv<T>(rows: T[], cols: CsvColumn<T>[]): string {
  const lines = [cols.map((c) => cell(c.header)).join(',')]
  for (const r of rows) lines.push(cols.map((c) => cell(c.value(r))).join(','))
  return '﻿' + lines.join('\r\n') + '\r\n'
}

export function downloadCsv(filename: string, text: string): void {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
