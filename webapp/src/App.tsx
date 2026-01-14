import { Routes, Route, NavLink } from 'react-router-dom'
import { useData } from './hooks/useData'
import { cn } from './lib/utils'
import MatrixPage from './pages/MatrixPage'
import TagsPage from './pages/TagsPage'
import ProductsPage from './pages/ProductsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import TagDetailPage from './pages/TagDetailPage'
import FeatureDetailPage from './pages/FeatureDetailPage'
import AdminPage from './pages/AdminPage'

function App() {
  const { tags, products, loading, error, reload } = useData()

  if (loading) {
    return (
      <div className="min-h-dvh flex items-center justify-center">
        <div className="text-lg text-gray-600">Loading data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-4">
        <div className="text-lg text-red-600">Error: {error}</div>
        <button
          onClick={reload}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-dvh bg-gray-50">
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-full mx-auto px-4">
          <div className="flex items-center justify-between h-14">
            <div className="font-semibold text-lg text-balance">Product Changelog Viewer</div>
            <div className="flex gap-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  cn(
                    'px-4 py-2 rounded text-sm',
                    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'
                  )
                }
              >
                Matrix
              </NavLink>
              <NavLink
                to="/tags"
                className={({ isActive }) =>
                  cn(
                    'px-4 py-2 rounded text-sm',
                    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'
                  )
                }
              >
                Tags
              </NavLink>
              <NavLink
                to="/products"
                className={({ isActive }) =>
                  cn(
                    'px-4 py-2 rounded text-sm',
                    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'
                  )
                }
              >
                Products
              </NavLink>
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  cn(
                    'px-4 py-2 rounded text-sm',
                    isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'
                  )
                }
              >
                Admin
              </NavLink>
            </div>
            <button
              onClick={reload}
              className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              aria-label="Refresh data"
            >
              Refresh
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-full mx-auto p-4">
        <Routes>
          <Route path="/" element={<MatrixPage tags={tags} products={products} />} />
          <Route path="/tags" element={<TagsPage tags={tags} products={products} />} />
          <Route path="/tags/:primaryTag" element={<TagDetailPage tags={tags} products={products} />} />
          <Route path="/tags/:primaryTag/:secondaryTag" element={<TagDetailPage tags={tags} products={products} />} />
          <Route path="/products" element={<ProductsPage products={products} />} />
          <Route path="/products/:productName" element={<ProductDetailPage products={products} />} />
          <Route
            path="/feature/:productName/:primaryTag/:secondaryTag"
            element={<FeatureDetailPage products={products} />}
          />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
