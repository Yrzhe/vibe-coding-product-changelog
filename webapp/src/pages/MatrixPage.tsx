import { useMemo, useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import * as XLSX from 'xlsx'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import type { Tag, Product } from '../types'
import { flattenTags, productHasTag } from '../hooks/useData'
import { cn } from '../lib/utils'

interface AISummary {
  last_updated: string
  matrix_overview: string
  tag_summaries: Record<string, string>
}

// 简单的 Markdown 渲染函数
function renderMarkdownText(text: string) {
  // 分割成行
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let currentParagraph: string[] = []
  
  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      const content = currentParagraph.join(' ')
      if (content.trim()) {
        elements.push(
          <p key={`p-${elements.length}`} className="text-sm text-blue-800 leading-relaxed mb-3">
            {processInlineMarkdown(content)}
          </p>
        )
      }
      currentParagraph = []
    }
  }
  
  // 处理内联 Markdown（加粗）
  const processInlineMarkdown = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-blue-900">{part.slice(2, -2)}</strong>
      }
      return part
    })
  }
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    
    // 空行 - 结束当前段落
    if (!line) {
      flushParagraph()
      continue
    }
    
    // 一级标题 # 
    if (line.startsWith('# ')) {
      flushParagraph()
      elements.push(
        <h3 key={`h1-${i}`} className="text-lg font-bold text-blue-900 mt-4 mb-3 first:mt-0 border-b border-blue-200 pb-2">
          {line.slice(2)}
        </h3>
      )
      continue
    }
    
    // 二级标题 ##
    if (line.startsWith('## ')) {
      flushParagraph()
      elements.push(
        <h4 key={`h2-${i}`} className="text-base font-semibold text-blue-900 mt-4 mb-2">
          {line.slice(3)}
        </h4>
      )
      continue
    }
    
    // 三级标题 ###
    if (line.startsWith('### ')) {
      flushParagraph()
      elements.push(
        <h5 key={`h3-${i}`} className="text-sm font-semibold text-blue-900 mt-3 mb-1">
          {line.slice(4)}
        </h5>
      )
      continue
    }
    
    // **加粗标题** 单独一行
    if (line.startsWith('**') && line.endsWith('**') && !line.slice(2, -2).includes('**')) {
      flushParagraph()
      elements.push(
        <h4 key={`bold-${i}`} className="text-base font-semibold text-blue-900 mt-4 mb-2">
          {line.slice(2, -2)}
        </h4>
      )
      continue
    }
    
    // 普通段落内容
    currentParagraph.push(line)
  }
  
  // 处理最后一个段落
  flushParagraph()
  
  return <>{elements}</>
}

interface AdminConfig {
  exclude_tags?: string[]
}

interface MatrixPageProps {
  tags: Tag[]
  products: Product[]
}

function MatrixPage({ tags, products }: MatrixPageProps) {
  const [excludeTags, setExcludeTags] = useState<string[]>([])
  const [expandedPrimaryTags, setExpandedPrimaryTags] = useState<Set<string>>(new Set())
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null)

  // 加载排除标签配置
  useEffect(() => {
    fetch('/data/info/admin_config.json')
      .then(res => res.ok ? res.json() : null)
      .then((config: AdminConfig | null) => {
        if (config?.exclude_tags) {
          setExcludeTags(config.exclude_tags)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/data/info/summary.json')
      .then(res => res.ok ? res.json() : null)
      .then(data => setAiSummary(data))
      .catch(() => {})
  }, [])

  // 过滤掉 exclude_tags 中的标签（包括顶级标签和 subtag）
  const filteredTags = useMemo(() => {
    return tags.filter(tag => !excludeTags.includes(tag.name))
  }, [tags, excludeTags])

  const tagRows = useMemo(() => {
    const allRows = flattenTags(filteredTags)
    // 过滤掉：
    // 1. exclude_tags 中的 subtag
    // 2. 没有任何产品使用的 subtag
    return allRows.filter(row => {
      // 排除 exclude_tags
      if (excludeTags.includes(row.secondaryTag)) return false
      // 排除没有任何产品使用的标签
      const hasAnyProduct = products.some(product => 
        productHasTag(product, row.primaryTag, row.secondaryTag)
      )
      return hasAnyProduct
    })
  }, [filteredTags, excludeTags, products])

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

      {/* AI Summary Overview */}
      {aiSummary?.matrix_overview && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-5">
          <div className="flex items-start gap-4">
            <div className="shrink-0 size-10 bg-blue-100 rounded-full flex items-center justify-center">
              <svg className="size-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-blue-900 mb-3">AI 竞品分析报告</h3>
              <div className="prose prose-sm prose-blue max-w-none">
                {renderMarkdownText(aiSummary.matrix_overview)}
              </div>
              {aiSummary.last_updated && (
                <p className="text-xs text-blue-500 mt-4 pt-3 border-t border-blue-200">
                  更新于 {new Date(aiSummary.last_updated).toLocaleDateString('zh-CN')}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

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
  const totalSubtags = rows.length
  
  // 计算每个产品覆盖的 subtag 数量
  const subtagCounts = useMemo(() => {
    return products.map(product => {
      const count = rows.filter(row => productHasTag(product, row.primaryTag, row.secondaryTag)).length
      return count
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
        {products.map((product, idx) => {
          const count = subtagCounts[idx]
          const percentage = totalSubtags > 0 ? count / totalSubtags : 0
          
          return (
            <td key={product.name} className="px-4 py-3 text-center">
              {count > 0 ? (
                <span 
                  className={cn(
                    "inline-block px-1.5 py-0.5 rounded text-xs font-medium",
                    percentage === 1 
                      ? "bg-green-100 text-green-700" 
                      : percentage >= 0.5 
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-gray-100 text-gray-600"
                  )}
                >
                  {count}/{totalSubtags}
                </span>
              ) : (
                <span className="text-gray-300">-</span>
              )}
            </td>
          )
        })}
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
