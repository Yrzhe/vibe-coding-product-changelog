import { useState, useEffect } from 'react'

interface Summary {
  last_updated: string
  matrix_overview: string
  tag_summaries: Record<string, string>
}

export function useSummary() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSummary()
  }, [])

  const loadSummary = async () => {
    setLoading(true)
    try {
      const response = await fetch('/data/info/summary.json')
      if (response.ok) {
        const data = await response.json()
        setSummary(data)
      }
    } catch {
      console.warn('Failed to load summary')
    } finally {
      setLoading(false)
    }
  }

  return { summary, loading, reload: loadSummary }
}

export function useMatrixOverview() {
  const { summary, loading } = useSummary()
  return {
    overview: summary?.matrix_overview || null,
    lastUpdated: summary?.last_updated || null,
    loading
  }
}

export function useTagSummary(tagName: string) {
  const { summary, loading } = useSummary()
  return {
    summary: summary?.tag_summaries?.[tagName] || null,
    loading
  }
}
