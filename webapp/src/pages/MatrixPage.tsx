import { useMemo, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import * as XLSX from 'xlsx'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import type { Tag, Product } from '../types'
import { flattenTags, productHasTag } from '../hooks/useData'
import { cn } from '../lib/utils'

interface MatrixPageProps {
  tags: Tag[]
  products: Product[]
}

function MatrixPage({ tags, products }: MatrixPageProps) {
  const tagRows = useMemo(() => flattenTags(tags), [tags])
  const [expandedPrimaryTags, setExpandedPrimaryTags] = useState<Set<string>>(new Set())

  // Group rows by primary tag
  const groupedRows = useMemo(() => {
    const groups = new Map<string, typeof tagRows>()
    for (const row of tagRows) {
      const existing = groups.get(row.primaryTag) || []
      existing.push(row)
      groups.set(row.primaryTag, existing)
    }
    return groups
  }, [tagRows])

  const togglePrimaryTag = (primaryTag: string) => {
    setExpandedPrimaryTags(prev => {
      const next = new Set(prev)
      if (next.has(primaryTag)) {
        next.delete(primaryTag)
      } else {
        next.add(primaryTag)
      }
      return next
    })
  }

  const expandAll = () => {
    setExpandedPrimaryTags(new Set(groupedRows.keys()))
  }

  const collapseAll = () => {
    setExpandedPrimaryTags(new Set())
  }

  const exportToExcel = useCallback(() => {
    // Build data array for Excel
    const headers = ['Primary Tag', 'Secondary Tag', ...products.map(p => p.name)]
    const data: (string | number)[][] = [headers]

    // Add all tag rows
    for (const row of tagRows) {
      const rowData: (string | number)[] = [
        row.primaryTag,
        row.secondaryTag,
        ...products.map(product =>
          productHasTag(product, row.primaryTag, row.secondaryTag) ? '✓' : ''
        )
      ]
      data.push(rowData)
    }

    // Create workbook and worksheet
    const wb = XLSX.utils.book_new()
    const worksheet = XLSX.utils.aoa_to_sheet(data)

    // Set column widths
    const colWidths = [
      { wch: 20 }, // Primary Tag
      { wch: 25 }, // Secondary Tag
      ...products.map(() => ({ wch: 12 })) // Product columns
    ]
    worksheet['!cols'] = colWidths

    XLSX.utils.book_append_sheet(wb, worksheet, 'Tag-Product Matrix')

    // Generate filename with date
    const date = new Date().toISOString().split('T')[0]
    const filename = `tag-product-matrix-${date}.xlsx`

    // Download file
    XLSX.writeFile(wb, filename)
  }, [tagRows, products])

  const downloadAllData = useCallback(async () => {
    const zip = new JSZip()

    // Fetch and add info files
    const infoFolder = zip.folder('info')
    try {
      const tagResponse = await fetch('/data/info/tag.json')
      if (tagResponse.ok) {
        const tagData = await tagResponse.text()
        infoFolder?.file('tag.json', tagData)
      }

      const competitorResponse = await fetch('/data/info/competitor.json')
      if (competitorResponse.ok) {
        const competitorData = await competitorResponse.text()
        infoFolder?.file('competitor.json', competitorData)
      }
    } catch (e) {
      console.error('Failed to fetch info files:', e)
    }

    // Fetch and add storage files
    const storageFolder = zip.folder('storage')
    for (const product of products) {
      try {
        const response = await fetch(`/data/storage/${product.name}.json`)
        if (response.ok) {
          const data = await response.text()
          storageFolder?.file(`${product.name}.json`, data)
        }
      } catch (e) {
        console.error(`Failed to fetch ${product.name}.json:`, e)
      }
    }

    // Generate and download zip
    const content = await zip.generateAsync({ type: 'blob' })
    const date = new Date().toISOString().split('T')[0]
    saveAs(content, `changelog-data-${date}.zip`)
  }, [products])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-balance">Tag-Product Matrix</h1>
        <div className="flex gap-2">
          <button
            onClick={expandAll}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
          >
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
          >
            Collapse All
          </button>
          <button
            onClick={exportToExcel}
            className="px-3 py-1.5 text-sm text-white bg-green-600 hover:bg-green-700 rounded"
          >
            Export Excel
          </button>
          <button
            onClick={downloadAllData}
            className="px-3 py-1.5 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded"
          >
            Download All
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-auto max-h-[calc(100vh-180px)]">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0 z-20">
            <tr>
              <th className="sticky left-0 z-30 bg-gray-50 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-40 border-b border-gray-200">
                Primary Tag
              </th>
              <th className="sticky left-40 z-30 bg-gray-50 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-40 border-r border-b border-gray-200">
                Secondary Tag
              </th>
              {products.map(product => (
                <th
                  key={product.name}
                  className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-24 bg-gray-50 border-b border-gray-200"
                >
                  <Link
                    to={`/products/${encodeURIComponent(product.name)}`}
                    className="hover:text-blue-600"
                  >
                    {product.name}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {Array.from(groupedRows.entries()).map(([primaryTag, rows]) => {
              const isExpanded = expandedPrimaryTags.has(primaryTag)

              return (
                <PrimaryTagGroup
                  key={primaryTag}
                  primaryTag={primaryTag}
                  rows={rows}
                  products={products}
                  isExpanded={isExpanded}
                  onToggle={() => togglePrimaryTag(primaryTag)}
                />
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="text-sm text-gray-500 text-pretty">
        Click on a checkmark to view details. Click on a primary tag row to expand/collapse subtags.
      </p>
    </div>
  )
}

interface PrimaryTagGroupProps {
  primaryTag: string
  rows: ReturnType<typeof flattenTags>
  products: Product[]
  isExpanded: boolean
  onToggle: () => void
}

function PrimaryTagGroup({ primaryTag, rows, products, isExpanded, onToggle }: PrimaryTagGroupProps) {
  // Collapsed summary row
  const summaryCounts = useMemo(() => {
    return products.map(product => {
      return rows.some(row => productHasTag(product, row.primaryTag, row.secondaryTag))
    })
  }, [products, rows])

  if (!isExpanded) {
    return (
      <tr className="hover:bg-gray-50 cursor-pointer" onClick={onToggle}>
        <td className="sticky left-0 bg-white px-4 py-3 text-sm font-medium text-gray-900 min-w-40">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">+</span>
            <Link
              to={`/tags/${encodeURIComponent(primaryTag)}`}
              className="hover:text-blue-600"
              onClick={e => e.stopPropagation()}
            >
              {primaryTag}
            </Link>
            <span className="text-xs text-gray-400">({rows.length})</span>
          </div>
        </td>
        <td className="sticky left-40 bg-white px-4 py-3 text-sm text-gray-500 min-w-40 border-r border-gray-200">
          {rows.length} subtags
        </td>
        {products.map((product, idx) => (
          <td key={product.name} className="px-4 py-3 text-center">
            {summaryCounts[idx] && (
              <span className="inline-block size-5 bg-green-100 text-green-700 rounded text-xs leading-5">
                *
              </span>
            )}
          </td>
        ))}
      </tr>
    )
  }

  // Expanded rows
  return (
    <>
      {rows.map((row, idx) => (
        <tr
          key={`${row.primaryTag}-${row.secondaryTag}`}
          className={cn('hover:bg-gray-50', idx === 0 && 'cursor-pointer')}
          onClick={idx === 0 ? onToggle : undefined}
        >
          <td className="sticky left-0 bg-white px-4 py-3 text-sm text-gray-900 min-w-40">
            {idx === 0 ? (
              <div className="flex items-center gap-2 font-medium">
                <span className="text-gray-400">-</span>
                <Link
                  to={`/tags/${encodeURIComponent(primaryTag)}`}
                  className="hover:text-blue-600"
                  onClick={e => e.stopPropagation()}
                >
                  {row.primaryTag}
                </Link>
              </div>
            ) : null}
          </td>
          <td className="sticky left-40 bg-white px-4 py-3 text-sm text-gray-600 min-w-40 border-r border-gray-200">
            <Link
              to={`/tags/${encodeURIComponent(row.primaryTag)}/${encodeURIComponent(row.secondaryTag)}`}
              className="hover:text-blue-600"
            >
              {row.secondaryTag}
            </Link>
          </td>
          {products.map(product => {
            const hasTag = productHasTag(product, row.primaryTag, row.secondaryTag)
            return (
              <td key={product.name} className="px-4 py-3 text-center">
                {hasTag ? (
                  <Link
                    to={`/feature/${encodeURIComponent(product.name)}/${encodeURIComponent(row.primaryTag)}/${encodeURIComponent(row.secondaryTag)}`}
                    className="inline-flex items-center justify-center size-5 bg-green-500 text-white rounded hover:bg-green-600"
                    aria-label={`View ${product.name} features for ${row.secondaryTag}`}
                  >
                    <svg className="size-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </Link>
                ) : (
                  <span className="inline-block size-5 text-gray-300">-</span>
                )}
              </td>
            )
          })}
        </tr>
      ))}
    </>
  )
}

export default MatrixPage
