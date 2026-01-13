export interface Subtag {
  name: string
  description?: string
}

export interface Tag {
  name: string
  description?: string
  subtags: Subtag[]
}

export interface FeatureTag {
  name: string
  subtags: { name: string }[]
}

export interface Feature {
  title: string
  description: string
  time: string
  tags: FeatureTag[]
}

export interface ProductData {
  name: string
  url?: string
  features?: Feature[]
}

export interface Product {
  name: string
  url: string
  features: Feature[]
}

// Flattened tag row for the matrix view
export interface TagRow {
  primaryTag: string
  secondaryTag: string
  primaryDescription?: string
  secondaryDescription?: string
}

// Product-tag mapping
export interface ProductTagMatrix {
  tags: TagRow[]
  products: Product[]
}
