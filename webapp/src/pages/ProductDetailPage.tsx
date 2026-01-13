import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { Product } from '../types'

interface ProductDetailPageProps {
  products: Product[]
}

function ProductDetailPage({ products }: ProductDetailPageProps) {
  const { productName } = useParams<{ productName: string }>()
  const decodedName = productName ? decodeURIComponent(productName) : ''

  const product = products.find(p => p.name === decodedName)

  // Sort features by time (newest first)
  const sortedFeatures = useMemo(() => {
    if (!product) return []

    return [...product.features].sort((a, b) => {
      const dateA = parseDate(a.time)
      const dateB = parseDate(b.time)
      return dateB.getTime() - dateA.getTime()
    })
  }, [product])

  // Group features by time period
  const groupedFeatures = useMemo(() => {
    const groups = new Map<string, typeof sortedFeatures>()
    for (const feature of sortedFeatures) {
      const existing = groups.get(feature.time) || []
      existing.push(feature)
      groups.set(feature.time, existing)
    }
    return groups
  }, [sortedFeatures])

  if (!product) {
    return (
      <div className="space-y-6">
        <Link to="/products" className="text-sm text-blue-600 hover:text-blue-700">
          Back to Products
        </Link>
        <p className="text-gray-500 text-pretty">Product not found: {decodedName}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/products" className="hover:text-blue-600">Products</Link>
        <span>/</span>
        <span className="text-gray-900">{product.name}</span>
      </div>

      <div>
        <h1 className="text-xl font-semibold text-balance">{product.name} Changelog</h1>
        {product.url && (
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 text-sm text-blue-600 hover:text-blue-700"
          >
            {product.url}
          </a>
        )}
        <p className="mt-2 text-gray-600">{product.features.length} features tracked</p>
      </div>

      <div className="space-y-8">
        {Array.from(groupedFeatures.entries()).map(([timePeriod, features]) => (
          <div key={timePeriod} className="space-y-4">
            <h2 className="text-lg font-medium text-gray-900 text-balance border-b border-gray-200 pb-2">
              {timePeriod}
            </h2>
            <div className="space-y-3">
              {features.map((feature, idx) => (
                <div
                  key={`${feature.title}-${idx}`}
                  className="p-4 bg-white rounded-lg border border-gray-200"
                >
                  <h3 className="font-medium text-gray-900 text-balance">{feature.title}</h3>
                  <p className="mt-1 text-sm text-gray-600 text-pretty">{feature.description}</p>
                  {Array.isArray(feature.tags) && feature.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
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
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Parse date from various formats
function parseDate(dateStr: string): Date {
  const isoMatch = dateStr.match(/\d{4}-\d{2}-\d{2}/)
  if (isoMatch) return new Date(isoMatch[0])

  const dateMatch = dateStr.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/)
  if (dateMatch) return new Date(`${dateMatch[3]}-${dateMatch[1]}-${dateMatch[2]}`)

  return new Date(0)
}

export default ProductDetailPage
