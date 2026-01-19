import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import type { Tag, Product } from '../types'
import { getSubtags, getTagFeatures } from '../hooks/useData'

interface AdminConfig {
  exclude_tags?: string[]
}

interface TagsPageProps {
  tags: Tag[]
  products: Product[]
}

function TagsPage({ tags, products }: TagsPageProps) {
  const [excludeTags, setExcludeTags] = useState<string[]>([])

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

  // 过滤掉 exclude_tags 中的标签
  const filteredTags = useMemo(() => {
    return tags.filter(tag => !excludeTags.includes(tag.name))
  }, [tags, excludeTags])

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-balance">Browse by Tag</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredTags.map(tag => {
          // 获取 subtags 并过滤掉：
          // 1. exclude_tags 中的
          // 2. 没有任何产品使用的
          const allSubtags = getSubtags(tags, tag.name)
          const subtags = allSubtags.filter(st => {
            if (excludeTags.includes(st)) return false
            // 检查是否有任何产品使用这个 subtag
            const features = getTagFeatures(products, tag.name, st)
            return features.length > 0
          })
          const totalFeatures = subtags.reduce((sum, st) => {
            return sum + getTagFeatures(products, tag.name, st).length
          }, 0)

          return (
            <Link
              key={tag.name}
              to={`/tags/${encodeURIComponent(tag.name)}`}
              className="block p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm"
            >
              <h2 className="font-medium text-gray-900 text-balance">{tag.name}</h2>
              {tag.description && (
                <p className="mt-1 text-sm text-gray-500 text-pretty line-clamp-2">{tag.description}</p>
              )}
              <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
                <span>{subtags.length} subtags</span>
                <span>{totalFeatures} features</span>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export default TagsPage
