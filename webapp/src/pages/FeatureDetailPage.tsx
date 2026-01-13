import { useParams, Link } from 'react-router-dom'
import type { Product } from '../types'
import { getProductTagFeatures } from '../hooks/useData'

interface FeatureDetailPageProps {
  products: Product[]
}

function FeatureDetailPage({ products }: FeatureDetailPageProps) {
  const { productName, primaryTag, secondaryTag } = useParams<{
    productName: string
    primaryTag: string
    secondaryTag: string
  }>()

  const decodedProduct = productName ? decodeURIComponent(productName) : ''
  const decodedPrimaryTag = primaryTag ? decodeURIComponent(primaryTag) : ''
  const decodedSecondaryTag = secondaryTag ? decodeURIComponent(secondaryTag) : ''

  const product = products.find(p => p.name === decodedProduct)

  if (!product) {
    return (
      <div className="space-y-6">
        <Link to="/" className="text-sm text-blue-600 hover:text-blue-700">
          Back to Matrix
        </Link>
        <p className="text-gray-500 text-pretty">Product not found: {decodedProduct}</p>
      </div>
    )
  }

  const features = getProductTagFeatures(product, decodedPrimaryTag, decodedSecondaryTag)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/" className="hover:text-blue-600">Matrix</Link>
        <span>/</span>
        <Link to={`/products/${encodeURIComponent(product.name)}`} className="hover:text-blue-600">
          {product.name}
        </Link>
        <span>/</span>
        <Link to={`/tags/${encodeURIComponent(decodedPrimaryTag)}`} className="hover:text-blue-600">
          {decodedPrimaryTag}
        </Link>
        <span>/</span>
        <span className="text-gray-900">{decodedSecondaryTag}</span>
      </div>

      <div>
        <h1 className="text-xl font-semibold text-balance">
          {product.name}: {decodedPrimaryTag} / {decodedSecondaryTag}
        </h1>
        <p className="mt-2 text-gray-600">{features.length} features</p>
      </div>

      <div className="space-y-4">
        {features.length === 0 ? (
          <p className="text-gray-500 text-pretty">No features found for this combination.</p>
        ) : (
          features.map((feature, idx) => (
            <div
              key={`${feature.title}-${idx}`}
              className="p-4 bg-white rounded-lg border border-gray-200"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-900 text-balance">{feature.title}</h3>
                  <p className="mt-2 text-sm text-gray-600 text-pretty whitespace-pre-wrap">
                    {feature.description}
                  </p>
                </div>
                <div className="flex-shrink-0 text-right">
                  <p className="text-xs text-gray-400 tabular-nums">{feature.time}</p>
                </div>
              </div>

              {Array.isArray(feature.tags) && feature.tags.length > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-2">All tags for this feature:</p>
                  <div className="flex flex-wrap gap-2">
                    {feature.tags.map((tag, tagIdx) => (
                      <span key={tagIdx} className="inline-flex items-center gap-1">
                        <Link
                          to={`/tags/${encodeURIComponent(tag.name)}`}
                          className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                        >
                          {tag.name}
                        </Link>
                        {Array.isArray(tag.subtags) && tag.subtags.length > 0 && (
                          <span className="text-xs text-gray-400">
                            ({tag.subtags.map(st => st.name).join(', ')})
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="flex gap-4">
        <Link
          to={`/products/${encodeURIComponent(product.name)}`}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          View all {product.name} features
        </Link>
        <Link
          to={`/tags/${encodeURIComponent(decodedPrimaryTag)}/${encodeURIComponent(decodedSecondaryTag)}`}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          View all {decodedSecondaryTag} features
        </Link>
      </div>
    </div>
  )
}

export default FeatureDetailPage
