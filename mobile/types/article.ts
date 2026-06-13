export type CategoryKey =
  | 'models'
  | 'research'
  | 'tools'
  | 'cloud'
  | 'industry'
  | 'other';

export interface EntityMap {
  models: string[];
  companies: string[];
  techniques: string[];
  datasets: string[];
}

export interface Article {
  id: string;
  title: string;
  url: string;
  source: string;
  source_domain: string;
  published_at: string | null;
  ingested_at: string;
  summary: string | null;
  category: CategoryKey | null;
  importance: number | null;
  entities: EntityMap;
  keywords: string[];
  bookmarked: boolean;
  read_at: string | null;
  read_duration_s: number | null;
  quiz_attempted: boolean;
  personalized_score: number | null;
}

export interface FeedResponse {
  items: Article[];
  total: number;
  has_more: boolean;
  next_offset: number;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  results: Article[];
  total: number;
}

export type SearchMode = 'fts' | 'semantic' | 'hybrid';

export interface Digest {
  id: string;
  date: string;
  generated_at: string;
  headline: string | null;
  narrative: string | null;
  key_themes: string[];
  top_articles: Article[];
}

export interface DigestHistoryItem {
  date: string;
  headline: string | null;
}
