import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { Tag, Product } from '../types'
import { getSubtags, getTagFeatures } from '../hooks/useData'

interface TagDetailPageProps {
  tags: Tag[]
  products: Product[]
}

function TagDetailPage({ tags, products }: TagDetailPageProps) {
  const { primaryTag, secondaryTag } = useParams<{ primaryTag: string; secondaryTag?: string }>()

  const decodedPrimaryTag = primaryTag ? decodeURIComponent(primaryTag) : ''
  const decodedSecondaryTag = secondaryTag ? decodeURIComponent(secondaryTag) : ''

  const tagInfo = tags.find(t => t.name === decodedPrimaryTag)
  const subtags = useMemo(() => getSubtags(tags, decodedPrimaryTag), [tags, decodedPrimaryTag])

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
