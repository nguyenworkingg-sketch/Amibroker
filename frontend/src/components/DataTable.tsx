import {
  type ColumnDef, type SortingState, type VisibilityState, flexRender, getCoreRowModel, getPaginationRowModel,
  getSortedRowModel, useReactTable,
} from '@tanstack/react-table'
import { useState, type ReactNode } from 'react'

export type ColMeta = { align?: 'right'; title?: string }

interface Props<T> {
  data: T[]
  columns: ColumnDef<T, unknown>[]
  initialSort?: SortingState
  pageSize?: number
  empty?: ReactNode
  toolbar?: ReactNode
  rowKey?: (r: T) => string
  hiddenByDefault?: string[]
  maxHeight?: string
}

/** Bang du lieu: sap xep nhieu cot (Shift + bam tieu de), phan trang, an/hien cot, header dinh. */
export function DataTable<T>({ data, columns, initialSort = [], pageSize = 50, empty, toolbar, rowKey, hiddenByDefault = [], maxHeight = '70vh' }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSort)
  const [vis, setVis] = useState<VisibilityState>(() => Object.fromEntries(hiddenByDefault.map((k) => [k, false])))
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize })
  const [showCols, setShowCols] = useState(false)
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility: vis, pagination },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setVis,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: rowKey ? (r) => rowKey(r) : undefined,
    enableMultiSort: true,
    isMultiSortEvent: (e) => (e as MouseEvent).shiftKey,
    sortDescFirst: true,
    autoResetPageIndex: true,
  })
  const pages = table.getPageCount()
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">{toolbar}</div>
        <div className="relative flex items-center gap-2 text-[12px] text-muted">
          <span>{data.length.toLocaleString('vi-VN')} dòng</span>
          <button className="btn" onClick={() => setShowCols((x) => !x)} aria-expanded={showCols}>
            Cột
          </button>
          {showCols && (
            <div className="card absolute right-0 top-9 z-20 max-h-80 w-60 overflow-auto p-2 shadow-lg">
              {table.getAllLeafColumns().map((c) => (
                <label key={c.id} className="flex items-center gap-2 py-0.5 text-[12.5px] text-fg">
                  <input type="checkbox" checked={c.getIsVisible()} onChange={c.getToggleVisibilityHandler()} />
                  {typeof c.columnDef.header === 'string' ? c.columnDef.header : c.id}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight }}>
        <table className="dt">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const meta = h.column.columnDef.meta as ColMeta | undefined
                  const s = h.column.getIsSorted()
                  const idx = h.column.getSortIndex()
                  return (
                    <th
                      key={h.id}
                      className={`${meta?.align === 'right' ? 'r' : ''} ${h.column.getCanSort() ? 'cursor-pointer select-none hover:text-fg' : ''}`}
                      onClick={h.column.getToggleSortingHandler()}
                      title={meta?.title ?? (h.column.getCanSort() ? 'Bấm để sắp xếp; Shift + bấm để sắp theo nhiều cột' : undefined)}
                      aria-sort={s === 'asc' ? 'ascending' : s === 'desc' ? 'descending' : undefined}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {s && (
                        <span className="ml-1 text-accent">
                          {s === 'desc' ? '↓' : '↑'}
                          {sorting.length > 1 && <sup>{idx + 1}</sup>}
                        </span>
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id}>
                {r.getVisibleCells().map((c) => {
                  const meta = c.column.columnDef.meta as ColMeta | undefined
                  return (
                    <td key={c.id} className={meta?.align === 'right' ? 'r num' : ''}>
                      {flexRender(c.column.columnDef.cell, c.getContext())}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {data.length === 0 && <div className="p-6 text-center text-muted">{empty ?? 'Không có dòng nào khớp bộ lọc.'}</div>}
      </div>
      {pages > 1 && (
        <div className="mt-2 flex items-center justify-end gap-2 text-[12.5px] text-muted">
          <button className="btn" onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()}>«</button>
          <button className="btn" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>‹</button>
          <span>
            Trang {pagination.pageIndex + 1}/{pages}
          </span>
          <button className="btn" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>›</button>
          <button className="btn" onClick={() => table.setPageIndex(pages - 1)} disabled={!table.getCanNextPage()}>»</button>
          <select className="inp" value={pagination.pageSize} onChange={(e) => table.setPageSize(Number(e.target.value))}>
            {[25, 50, 100, 250].map((n) => (
              <option key={n} value={n}>
                {n}/trang
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}

/** Cot so: thieu du lieu luon nam CUOI bat ke chieu sap xep (khong coi thieu du lieu la 0). */
export function numCol<T>(
  id: string,
  header: string,
  get: (r: T) => number | null | undefined,
  render: (v: number | null | undefined, r: T) => ReactNode,
  title?: string,
): ColumnDef<T, unknown> {
  return {
    id,
    header,
    accessorFn: (r) => get(r) ?? undefined,
    sortUndefined: 'last',
    cell: ({ row }) => render(get(row.original), row.original),
    meta: { align: 'right', title } satisfies ColMeta,
  }
}

export function textCol<T>(id: string, header: string, get: (r: T) => string | null | undefined, render?: (r: T) => ReactNode): ColumnDef<T, unknown> {
  return {
    id,
    header,
    accessorFn: (r) => get(r) ?? undefined,
    sortUndefined: 'last',
    sortDescFirst: false,
    cell: ({ row }) => (render ? render(row.original) : get(row.original) ?? '—'),
  }
}
