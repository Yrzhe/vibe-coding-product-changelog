import { useMemo, useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { Tag, Product } from '../types'
import { getSubtags, getTagFeatures } from '../hooks/useData'

interface AdminConfig {
  exclude_tags?: string[]
}

interface AISummary {
  last_updated: string
  matrix_overview: string
  tag_summaries: Record<string, string>
}

// 简单的 Markdown 渲染函数
function renderMarkdownText(text: string) {
  // 处理加粗和换行
  const processText = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
      }
      const lines = part.split('\n')
      return lines.map((line, j) => (
        <span key={`${i}-${j}`}>
          {line}
          {j < lines.length - 1 && <br />}
        </span>
      ))
    })
  }
  
  return <>{processText(text)}</>
}

interface TagDetailPageProps {
  tags: Tag[]
  products: Product[]
}

function TagDetailPage({ tags, products }: TagDetailPageProps) {
  const { primaryTag, secondaryTag } = useParams<{ primaryTag: string; secondaryTag?: string }>()
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null)
  const [excludeTags, setExcludeTags] = useState<string[]>([])

  const decodedPrimaryTag = primaryTag ? decodeURIComponent(primaryTag) : ''
  const decodedSecondaryTag = secondaryTag ? decodeURIComponent(secondaryTag) : ''

  const tagInfo = tags.find(t => t.name === decodedPrimaryTag)
  const allSubtags = useMemo(() => getSubtags(tags, decodedPrimaryTag), [tags, decodedPrimaryTag])
  
  // 过滤掉 exclude_tags 中的 subtag
  const subtags = useMemo(() => {
    return allSubtags.filter(st => !excludeTags.includes(st))
  }, [allSubtags, excludeTags])

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

  // If no secondary tag, show list of subtags
  if (!decodedSecondaryTag) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link to="/tags" className="hover:text-blue-600">Tags</Link>
          <span>/</span>
          <span className="text-gray-900">{decodedPrimaryTag}</span>
        </div>

        <div>
          <h1 className="text-xl font-semibold text-balance">{decodedPrimaryTag}</h1>
          {tagInfo?.description && (
            <p className="mt-2 text-gray-600 text-pretty">{tagInfo.description}</p>
          )}
        </div>

        {/* AI Tag Summary */}
        {aiSummary?.tag_summaries?.[decodedPrimaryTag] && (
          <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200 p-4">
            <div className="flex items-start gap-3">
              <div className="shrink-0 size-8 bg-purple-100 rounded-full flex items-center justify-center">
                <svg className="size-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-purple-900 mb-2">AI 标签分析</h3>
                <div className="text-sm text-purple-800 leading-relaxed">
                  {renderMarkdownText(aiSummary.tag_summaries[decodedPrimaryTag])}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <h2 className="text-lg font-medium text-balance">Subtags</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {subtags.map(subtag => {
              const features = getTagFeatures(products, decodedPrimaryTag, subtag)
              return (
                <Link
                  key={subtag}
                  to={`/tags/${encodeURIComponent(decodedPrimaryTag)}/${encodeURIComponent(subtag)}`}
                  className="block p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm"
                >
                  <h3 className="font-medium text-gray-900 text-balance">{subtag}</h3>
                  <p className="mt-2 text-sm text-gray-400">{features.length} features</p>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // Show features for specific secondary tag
  const features = getTagFeatures(products, decodedPrimaryTag, decodedSecondaryTag)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/tags" className="hover:text-blue-600">Tags</Link>
        <span>/</span>
        <Link to={`/tags/${encodeURIComponent(decodedPrimaryTag)}`} className="hover:text-blue-600">
          {decodedPrimaryTag}
        </Link>
        <span>/</span>
        <span className="text-gray-900">{decodedSecondaryTag}</span>
      </div>

      <div>
        <h1 className="text-xl font-semibold text-balance">
          {decodedPrimaryTag} / {decodedSecondaryTag}
        </h1>
        <p className="mt-2 text-gray-600">{features.length} features from {new Set(features.map(f => f.product.name)).size} products</p>
      </div>

      <div className="space-y-4">
        {features.length === 0 ? (
          <p className="text-gray-500 text-pretty">No features found for this tag combination.</p>
        ) : (
          features.map((item, idx) => (
            <div
              key={`${item.product.name}-${item.feature.title}-${idx}`}
              className="p-4 bg-white rounded-lg border border-gray-200"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 text-balance">{item.feature.title}</h3>
                  <p className="mt-1 text-sm text-gray-600 text-pretty">{item.feature.description}</p>
                </div>
                <div className="flex-shrink-0 text-right">
                  <Link
                    to={`/products/${encodeURIComponent(item.product.name)}`}
                    className="text-sm font-medium text-blue-600 hover:text-blue-700"
                  >
                    {item.product.name}
                  </Link>
                  <p className="mt-1 text-xs text-gray-400 tabular-nums">{item.feature.time}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default TagDetailPage
