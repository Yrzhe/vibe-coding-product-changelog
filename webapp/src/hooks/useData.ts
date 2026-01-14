import { useState, useEffect, useCallback } from 'react'
import type { Tag, Product, ProductData, TagRow } from '../types'

// Storage file names to load (without .json extension)
// YouWare is our own product, placed first
const STORAGE_FILES = ['youware', 'base44', 'bolt', 'lovable', 'replit', 'rocket', 'trickle', 'v0']

export function useData() {
  const [tags, setTags] = useState<Tag[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Load tags
      const tagsResponse = await fetch('/data/info/tag.json')
      if (!tagsResponse.ok) throw new Error('Failed to load tags')
      const tagsData: Tag[] = await tagsResponse.json()
      setTags(tagsData)

      // Load all product files
      const productPromises = STORAGE_FILES.map(async (fileName) => {
        try {
          const response = await fetch(`/data/storage/${fileName}.json`)
          if (!response.ok) return null
          const data: ProductData[] = await response.json()

          // Extract app info and features
          const appInfo = data.find(item => item.name !== 'feature')
          const featureData = data.find(item => item.name === 'feature')

          if (!appInfo) return null

          return {
            name: appInfo.name,
            url: appInfo.url || '',
            features: featureData?.features || []
          } as Product
        } catch {
          console.warn(`Failed to load ${fileName}.json`)
          return null
        }
      })

      const loadedProducts = (await Promise.all(productPromises)).filter((p): p is Product => p !== null)
      setProducts(loadedProducts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return { tags, products, loading, error, reload: loadData }
}

// Helper to flatten tags into rows, including "Other" for tags without subtags
export function flattenTags(tags: Tag[]): TagRow[] {
  const rows: TagRow[] = []

  for (const tag of tags) {
    if (tag.subtags.length === 0) {
      // Tag without subtags - add "Other" as secondary
      rows.push({
        primaryTag: tag.name,
        secondaryTag: 'Other',
        primaryDescription: tag.description,
        secondaryDescription: tag.description
      })
    } else {
      for (const subtag of tag.subtags) {
        rows.push({
          primaryTag: tag.name,
          secondaryTag: subtag.name,
          primaryDescription: tag.description,
          secondaryDescription: subtag.description
        })
      }
    }
  }

  return rows
}

// Check if a product has a specific tag combination
export function productHasTag(product: Product, primaryTag: string, secondaryTag: string): boolean {
  for (const feature of product.features) {
    const tags = Array.isArray(feature.tags) ? feature.tags : []
    for (const tag of tags) {
      if (tag.name === primaryTag) {
        const subtags = tag.subtags || []
        // Handle "Other" case - when the primary tag has no subtags
        if (secondaryTag === 'Other') {
          if (subtags.length === 0) return true
        } else {
          if (subtags.some(st => st.name === secondaryTag)) return true
        }
      }
    }
  }
  return false
}

// Get all features for a specific product-tag combination
export function getProductTagFeatures(product: Product, primaryTag: string, secondaryTag: string) {
  return product.features.filter(feature => {
    const tags = Array.isArray(feature.tags) ? feature.tags : []
    return tags.some(tag => {
      if (tag.name !== primaryTag) return false
      const subtags = tag.subtags || []
      if (secondaryTag === 'Other') return subtags.length === 0
      return subtags.some(st => st.name === secondaryTag)
    })
  })
}

// Get all features for a tag across all products
export function getTagFeatures(products: Product[], primaryTag: string, secondaryTag: string) {
  const results: { product: Product; feature: Feature }[] = []

  for (const product of products) {
    const features = getProductTagFeatures(product, primaryTag, secondaryTag)
    for (const feature of features) {
      results.push({ product, feature })
    }
  }

  // Sort by date (newest first)
  return results.sort((a, b) => {
    const dateA = parseDate(a.feature.time)
    const dateB = parseDate(b.feature.time)
    return dateB.getTime() - dateA.getTime()
  })
}

// Parse date from various formats
function parseDate(dateStr: string): Date {
  // Try ISO date format first (YYYY-MM-DD)
  const isoMatch = dateStr.match(/\d{4}-\d{2}-\d{2}/)
  if (isoMatch) return new Date(isoMatch[0])

  // Try to extract any date-like pattern
  const dateMatch = dateStr.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/)
  if (dateMatch) return new Date(`${dateMatch[3]}-${dateMatch[1]}-${dateMatch[2]}`)

  // Return a very old date if unable to parse
  return new Date(0)
}

// Get unique primary tags from tags
export function getPrimaryTags(tags: Tag[]): string[] {
  return tags.map(t => t.name)
}

// Get subtags for a primary tag
export function getSubtags(tags: Tag[], primaryTag: string): string[] {
  const tag = tags.find(t => t.name === primaryTag)
  if (!tag) return []
  if (tag.subtags.length === 0) return ['Other']
  return tag.subtags.map(st => st.name)
}

type Feature = import('../types').Feature
