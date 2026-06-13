export interface Trend {
  name: string;
  mention_count: number;
  article_ids: string[];
  detected_at: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AskSource {
  id: string;
  title: string;
  url: string;
  similarity: number;
}

export interface AskResponse {
  answer: string;
  sources: AskSource[];
  used_groq: boolean;
}
