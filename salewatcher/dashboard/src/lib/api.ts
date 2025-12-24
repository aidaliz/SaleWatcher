const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
export interface Brand {
  id: string;
  name: string;
  milled_slug: string;
  is_active: boolean;
  excluded_categories: string[];
  created_at: string;
  updated_at: string;
}

export interface BrandCreate {
  name: string;
  milled_slug: string;
  excluded_categories?: string[];
}

export interface BrandUpdate {
  name?: string;
  milled_slug?: string;
  is_active?: boolean;
  excluded_categories?: string[];
}

export interface BrandListResponse {
  brands: Brand[];
  total: number;
  skip: number;
  limit: number;
}

export interface Prediction {
  id: string;
  brand_id: string;
  source_window_id: string;
  target_year: number;
  predicted_start: string;
  predicted_end: string;
  discount_type: string;
  expected_discount: number;
  discount_summary: string;
  categories: string[];
  confidence: number;
  synced_to_calendar: boolean;
  calendar_event_id: string | null;
  created_at: string;
  brand?: Brand;
}

export interface PredictionListResponse {
  predictions: Prediction[];
  total: number;
}

export interface ReviewItem {
  id: string;
  raw_email_id: string;
  brand_name: string;
  email_subject: string;
  sent_at: string;
  is_sale: boolean;
  discount_summary: string | null;
  confidence: number;
  model_used: string;
  extracted_at: string;
}

export interface ReviewListResponse {
  items: ReviewItem[];
  total: number;
}

export interface AccuracyStats {
  total_predictions: number;
  hits: number;
  misses: number;
  partials: number;
  pending: number;
  hit_rate: number;
  verified_count: number;
}

export interface BrandAccuracy {
  brand_id: string;
  brand_name: string;
  total_predictions: number;
  hits: number;
  misses: number;
  partials: number;
  hit_rate: number;
  reliability_tier: string;
}

// API Client with cache-busting
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // Add cache-busting timestamp
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  url.searchParams.set('_t', Date.now().toString());

  const response = await fetch(url.toString(), {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      ...options.headers,
    },
    cache: 'no-store',
    mode: 'cors',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Brands API
export const brandsApi = {
  list: (params?: { skip?: number; limit?: number; active_only?: boolean }) =>
    fetchAPI<BrandListResponse>(
      `/api/brands?skip=${params?.skip || 0}&limit=${params?.limit || 100}&active_only=${params?.active_only ?? true}`
    ),

  get: (id: string) => fetchAPI<Brand>(`/api/brands/${id}`),

  create: (data: BrandCreate) =>
    fetchAPI<Brand>('/api/brands', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: BrandUpdate) =>
    fetchAPI<Brand>(`/api/brands/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchAPI<void>(`/api/brands/${id}`, {
      method: 'DELETE',
    }),

  activate: (id: string) =>
    fetchAPI<Brand>(`/api/brands/${id}/activate`, {
      method: 'POST',
    }),
};

// Predictions API
export const predictionsApi = {
  list: (params?: { skip?: number; limit?: number; brand_id?: string; target_year?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.set('skip', params.skip.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.brand_id) searchParams.set('brand_id', params.brand_id);
    if (params?.target_year) searchParams.set('target_year', params.target_year.toString());
    return fetchAPI<PredictionListResponse>(`/api/predictions?${searchParams.toString()}`);
  },

  upcoming: (days: number = 7) =>
    fetchAPI<PredictionListResponse>(`/api/predictions/upcoming?days=${days}`),

  get: (id: string) => fetchAPI<Prediction>(`/api/predictions/${id}`),

  override: (id: string, result: 'hit' | 'miss' | 'partial', reason?: string) =>
    fetchAPI<Prediction>(`/api/predictions/${id}/override`, {
      method: 'POST',
      body: JSON.stringify({ result, reason }),
    }),
};

// Review API
export const reviewApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    fetchAPI<ReviewListResponse>(
      `/api/review?skip=${params?.skip || 0}&limit=${params?.limit || 50}`
    ),

  approve: (id: string, notes?: string) =>
    fetchAPI<{ status: string; id: string }>(`/api/review/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),

  reject: (id: string, notes?: string) =>
    fetchAPI<{ status: string; id: string }>(`/api/review/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
};

// Accuracy API
export const accuracyApi = {
  overall: () => fetchAPI<AccuracyStats>('/api/accuracy'),

  brands: () =>
    fetchAPI<{ brands: BrandAccuracy[] }>('/api/accuracy/brands'),

  suggestions: (status: string = 'pending') =>
    fetchAPI<any[]>(`/api/accuracy/suggestions?status=${status}`),
};
