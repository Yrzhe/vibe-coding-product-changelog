import { Link } from 'react-router-dom'
import type { Product } from '../types'

interface ProductsPageProps {
  products: Product[]
}

function ProductsPage({ products }: ProductsPageProps) {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-balance">Products</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {products.map(product => {
          // Count unique tags
          const tagSet = new Set<string>()
          for (const feature of product.features) {
            const tags = Array.isArray(feature.tags) ? feature.tags : []
            for (const tag of tags) {
              tagSet.add(tag.name)
            }
          }

          return (
            <Link
              key={product.name}
              to={`/products/${encodeURIComponent(product.name)}`}
              className="block p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm"
            >
              <h2 className="font-medium text-gray-900 text-balance">{product.name}</h2>
              {product.url && (
                <p className="mt-1 text-xs text-gray-400 truncate">{product.url}</p>
              )}
              <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
                <span>{product.features.length} features</span>
                <span>{tagSet.size} tags</span>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export default ProductsPage
