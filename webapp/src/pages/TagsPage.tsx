import { Link } from 'react-router-dom'
import type { Tag, Product } from '../types'
import { getSubtags, getTagFeatures } from '../hooks/useData'

interface TagsPageProps {
  tags: Tag[]
  products: Product[]
}

function TagsPage({ tags, products }: TagsPageProps) {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-balance">Browse by Tag</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {tags.map(tag => {
          const subtags = getSubtags(tags, tag.name)
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
