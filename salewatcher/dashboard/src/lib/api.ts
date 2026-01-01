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
export interface PredictionStats {
  total_predictions: number;
  upcoming_predictions: number;
  past_predictions: number;
  total_sale_windows: number;
  total_extracted_sales: number;
  by_brand: { brand_id: string; brand_name: string; predictions: number }[];
}

export interface GeneratePredictionsResponse {
  status: string;
  windows_created: number;
  predictions_created: number;
  message: string;
}

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

  stats: () => fetchAPI<PredictionStats>('/api/predictions/stats'),

  generate: (params?: { brand_id?: string; target_year?: number; years_ahead?: number }) =>
    fetchAPI<GeneratePredictionsResponse>('/api/predictions/generate', {
      method: 'POST',
      body: JSON.stringify(params || {}),
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

// Scrape Types
export interface ScrapeJob {
  id: string;
  brand_id: string;
  brand_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  emails_scraped: number;
  emails_extracted: number;
  predictions_generated: number;
  error: string | null;
  current_step: string;
}

export interface ScrapeRequest {
  days_back?: number;
  max_emails?: number;
  run_extraction?: boolean;
  run_predictions?: boolean;
}

export interface BrandStats {
  brand_id: string;
  brand_name: string;
  total_emails: number;
  extracted_sales: number;
  pending_review: number;
  predictions: number;
}

// Scrape API
export const scrapeApi = {
  startScrape: (brandSlug: string, request: ScrapeRequest = {}) =>
    fetchAPI<{ job_id: string; message: string }>(`/api/scrape/brand/${brandSlug}`, {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  getJob: (jobId: string) => fetchAPI<ScrapeJob>(`/api/scrape/jobs/${jobId}`),

  listJobs: () => fetchAPI<ScrapeJob[]>('/api/scrape/jobs'),

  getBrandStats: (brandSlug: string) =>
    fetchAPI<BrandStats>(`/api/scrape/brand/${brandSlug}/stats`),
};

// Gmail Types
export interface GmailStatus {
  configured: boolean;
  authenticated: boolean;
  message: string;
}

export interface GmailSyncResponse {
  status: string;
  message: string;
  stats?: {
    new?: number;
    duplicates?: number;
    errors?: number;
  };
}

// Gmail API
export const gmailApi = {
  getStatus: () => fetchAPI<GmailStatus>('/api/email/gmail/status'),

  configure: (clientId: string, clientSecret: string) =>
    fetchAPI<{ success: boolean; message: string }>('/api/email/gmail/configure', {
      method: 'POST',
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
    }),

  startAuth: () => fetchAPI<{ auth_url: string; state: string }>('/api/email/gmail/auth/start'),

  disconnect: () =>
    fetchAPI<{ status: string; message: string }>('/api/email/gmail/disconnect', {
      method: 'POST',
    }),

  syncBrand: (brandId: string, daysBack: number = 365, maxEmails: number = 500) =>
    fetchAPI<GmailSyncResponse>(`/api/email/sync/brand/${brandId}`, {
      method: 'POST',
      body: JSON.stringify({ days_back: daysBack, max_emails: maxEmails }),
    }),

  syncAll: (daysBack: number = 365, maxEmails: number = 500) =>
    fetchAPI<GmailSyncResponse>('/api/email/sync/all', {
      method: 'POST',
      body: JSON.stringify({ days_back: daysBack, max_emails: maxEmails }),
    }),
};

// Email Types
export interface Email {
  id: string;
  brand_id: string;
  brand_name: string;
  subject: string;
  sent_at: string;
  source: 'gmail' | 'milled';
  scraped_at: string;
  is_extracted: boolean;
  is_sale: boolean | null;
  discount_summary: string | null;
  confidence: number | null;
  review_status: string | null;
}

export interface EmailListResponse {
  emails: Email[];
  total: number;
  skip: number;
  limit: number;
}

export interface EmailStats {
  total_emails: number;
  gmail_emails: number;
  milled_emails: number;
  extracted: number;
  not_extracted: number;
  sales_found: number;
  non_sales: number;
  pending_review: number;
  by_brand: Array<{
    brand_id: string;
    brand_name: string;
    total: number;
    gmail: number;
    milled: number;
  }>;
}

export interface EmailDetail {
  id: string;
  brand_id: string;
  brand_name: string;
  subject: string;
  sent_at: string;
  source: string;
  scraped_at: string;
  html_content: string;
  milled_url: string;
  is_extracted: boolean;
  is_sale: boolean | null;
  discount_type: string | null;
  discount_value: number | null;
  discount_summary: string | null;
  categories: string[] | null;
  sale_start: string | null;
  sale_end: string | null;
  confidence: number | null;
  status: string | null;
}

// Emails API
export const emailsApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    brand_id?: string;
    source?: 'gmail' | 'milled';
    extracted?: boolean;
    is_sale?: boolean;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.set('skip', params.skip.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.brand_id) searchParams.set('brand_id', params.brand_id);
    if (params?.source) searchParams.set('source', params.source);
    if (params?.extracted !== undefined) searchParams.set('extracted', params.extracted.toString());
    if (params?.is_sale !== undefined) searchParams.set('is_sale', params.is_sale.toString());
    return fetchAPI<EmailListResponse>(`/api/emails?${searchParams.toString()}`);
  },

  stats: () => fetchAPI<EmailStats>('/api/emails/stats'),

  get: (id: string) => fetchAPI<EmailDetail>(`/api/emails/${id}`),

  extract: (id: string) =>
    fetchAPI<{ status: string; message: string; result: any }>(`/api/emails/${id}/extract`, {
      method: 'POST',
    }),

  extractBatch: (params: { brand_id?: string; limit?: number; reprocess?: boolean }) =>
    fetchAPI<{ status: string; total: number; processed: number; errors: number; message: string }>(
      '/api/emails/extract-batch',
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    ),

  updateExtraction: (id: string, params: { is_sale?: boolean; notes?: string }) =>
    fetchAPI<{ status: string; message: string; is_sale: boolean }>(
      `/api/emails/${id}/extraction`,
      {
        method: 'PATCH',
        body: JSON.stringify(params),
      }
    ),
};
