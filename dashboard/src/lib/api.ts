/**
 * API client for SaleWatcher backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Debug: Log API URL in browser console (only once)
if (typeof window !== 'undefined') {
  console.log('[SaleWatcher] API URL:', API_BASE_URL);

  if (!API_BASE_URL.startsWith('http://') && !API_BASE_URL.startsWith('https://')) {
    console.error(
      `[SaleWatcher] Invalid NEXT_PUBLIC_API_URL: "${API_BASE_URL}". ` +
      `URL must start with http:// or https://. ` +
      `Example: https://your-backend.up.railway.app`
    );
  }
}

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE_URL}${endpoint}`;

  // Build query params
  const searchParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
  }

  // Add cache-busting timestamp for GET requests
  if (!fetchOptions.method || fetchOptions.method === 'GET') {
    searchParams.append('_t', String(Date.now()));
  }

  const queryString = searchParams.toString();
  if (queryString) {
    url += `?${queryString}`;
  }

  console.log('[SaleWatcher] Fetching:', fetchOptions.method || 'GET', url);

  const response = await fetch(url, {
    ...fetchOptions,
    cache: 'no-store',
    mode: 'cors',
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      ...fetchOptions.headers,
    },
  });

  console.log('[SaleWatcher] Response status:', response.status, response.statusText);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    console.error('[SaleWatcher] API Error:', error);
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const data = await response.json();
  console.log('[SaleWatcher] Response data:', JSON.stringify(data).slice(0, 500));
  return data;
}

// Brand API
export const brandsApi = {
  list: (params?: { skip?: number; limit?: number; active_only?: boolean }) =>
    fetchApi<{ brands: Brand[]; total: number }>('/api/brands', { params }),

  get: (id: string) => fetchApi<Brand>(`/api/brands/${id}`),

  create: (data: BrandCreate) =>
    fetchApi<Brand>('/api/brands', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: BrandUpdate) =>
    fetchApi<Brand>(`/api/brands/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchApi<void>(`/api/brands/${id}`, { method: 'DELETE' }),
};

// Predictions API
export const predictionsApi = {
  list: (params?: { skip?: number; limit?: number; brand_id?: string }) =>
    fetchApi<{ predictions: Prediction[]; total: number }>('/api/predictions', {
      params,
    }),

  upcoming: (days = 14) =>
    fetchApi<{ predictions: Prediction[]; total: number }>(
      '/api/predictions/upcoming',
      { params: { days } }
    ),

  get: (id: string) => fetchApi<Prediction>(`/api/predictions/${id}`),

  override: (id: string, result: string, reason?: string) =>
    fetchApi<void>(`/api/predictions/${id}/override`, {
      method: 'POST',
      body: JSON.stringify({ result, reason }),
    }),
};

// Review API
export const reviewApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    fetchApi<{ reviews: ExtractedSale[]; total: number }>('/api/review', {
      params,
    }),

  approve: (id: string) =>
    fetchApi<void>(`/api/review/${id}/approve`, { method: 'POST' }),

  reject: (id: string) =>
    fetchApi<void>(`/api/review/${id}/reject`, { method: 'POST' }),
};

// Accuracy API
export const accuracyApi = {
  overall: () => fetchApi<AccuracyStats>('/api/accuracy'),

  brands: () =>
    fetchApi<{ brands: BrandAccuracy[] }>('/api/accuracy/brands'),

  suggestions: () =>
    fetchApi<{ suggestions: Suggestion[]; total: number }>('/api/accuracy/suggestions'),

  approveSuggestion: (id: string) =>
    fetchApi<void>(`/api/accuracy/suggestions/${id}/approve`, { method: 'POST' }),

  dismissSuggestion: (id: string) =>
    fetchApi<void>(`/api/accuracy/suggestions/${id}/dismiss`, { method: 'POST' }),
};

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

export interface Prediction {
  id: string;
  brand_id: string;
  brand?: {
    id: string;
    name: string;
  };
  source_window_id: string;
  predicted_start: string;
  predicted_end: string;
  discount_summary: string;
  milled_reference_url: string | null;
  confidence: number;
  calendar_event_id: string | null;
  notified_at: string | null;
  created_at?: string;
}

export interface ExtractedSale {
  id: string;
  email_id: string;
  brand_name: string;
  email_subject: string;
  discount_type: string;
  discount_value: number | null;
  discount_max: number | null;
  is_sitewide: boolean;
  categories: string[];
  confidence: number;
  raw_discount_text: string | null;
  model_used: string | null;
}

export interface AccuracyStats {
  total_predictions: number;
  correct_predictions: number;
  hit_rate: number;
  avg_timing_delta_days: number | null;
}

export interface BrandAccuracy {
  brand_id: string;
  total_predictions: number;
  correct_predictions: number;
  hit_rate: number;
  avg_timing_delta_days: number | null;
  reliability_tier: 'excellent' | 'good' | 'fair' | 'poor';
}

export interface Suggestion {
  id: string;
  brand_id: string;
  suggestion_type: string;
  description: string;
  recommended_action: string;
  status: 'pending' | 'approved' | 'dismissed';
  created_at: string;
}
