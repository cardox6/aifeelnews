import { getIdToken } from "./firebase";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8002";

export type ArticleDto = {
  id: number;
  title: string;
  description: string | null;
  url: string;
  image_url: string | null;
  published_at: string;
  source: {
    id: number;
    name: string;
  };
  sentiment_label?: string | null;
  sentiment_score?: number | null;
  language?: string | null;
  country?: string | null;
  category?: string | null;
};

export async function fetchLatestArticles(limit = 40): Promise<ArticleDto[]> {
  const url = `${API_BASE}/articles/latest?limit=${limit}`;
  console.log('Fetching from:', url);

  const res = await fetch(url);
  console.log('Response status:', res.status);

  if (!res.ok) {
    const errorText = await res.text();
    console.error('API Error:', errorText);
    throw new Error(`Failed to fetch latest articles: ${res.status} ${errorText}`);
  }

  const data = await res.json();
  console.log('API Response:', data);
  return data;
}

export async function fetchBookmarks(): Promise<any[]> {
  const token = await getIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_BASE}/bookmarks`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!res.ok) throw new Error("Failed to fetch bookmarks");
  return await res.json();
}
