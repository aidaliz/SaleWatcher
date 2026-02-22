'use client';

import { useEffect, useState } from 'react';
import { reviewApi, emailsApi, ReviewItem, EmailDetail } from '@/lib/api';

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Email preview modal
  const [previewItem, setPreviewItem] = useState<ReviewItem | null>(null);
  const [emailDetail, setEmailDetail] = useState<EmailDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    fetchReviewItems();
  }, []);

  // Close modal on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closePreview(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  async function fetchReviewItems() {
    try {
      setLoading(true);
      setError(null);
      const data = await reviewApi.list({ limit: 50 });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }

  const openPreview = async (item: ReviewItem) => {
    setPreviewItem(item);
    setEmailDetail(null);
    setPreviewLoading(true);
    try {
      const detail = await emailsApi.get(item.raw_email_id);
      setEmailDetail(detail);
    } catch {
      // show modal anyway, just without HTML
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewItem(null);
    setEmailDetail(null);
  };

  const handleApprove = async (id: string) => {
    setActionLoading(id);
    try {
      await reviewApi.approve(id);
      setItems(items.filter((item) => item.id !== id));
      setTotal(total - 1);
      if (previewItem?.id === id) closePreview();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: string) => {
    setActionLoading(id);
    try {
      await reviewApi.reject(id);
      setItems(items.filter((item) => item.id !== id));
      setTotal(total - 1);
      if (previewItem?.id === id) closePreview();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to reject');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading review queue...</div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Review Queue</h1>

      {error && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="text-gray-400 text-5xl mb-4">✓</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Review queue is empty</h2>
          <p className="text-gray-500">
            All extractions have been reviewed. New items will appear here when the LLM
            extracts low-confidence results that need human verification.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="bg-white rounded-lg shadow p-6">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2 flex-wrap">
                    <span className="font-semibold text-gray-900">{item.brand_name}</span>
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-semibold rounded-full ${
                        item.is_sale
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {item.is_sale ? 'Sale Detected' : 'No Sale'}
                    </span>
                    <span className="text-sm text-gray-500">
                      {Math.round(item.confidence * 100)}% confidence
                    </span>
                  </div>
                  <h3 className="text-lg text-gray-800 mb-2">{item.email_subject}</h3>
                  {item.discount_summary && (
                    <p className="text-sm text-gray-600 mb-2">{item.discount_summary}</p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span>Sent: {new Date(item.sent_at).toLocaleDateString()}</span>
                    <span>Model: {item.model_used}</span>
                    <span>Extracted: {new Date(item.extracted_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-2 mt-3 sm:mt-0 sm:ml-4">
                  <button
                    onClick={() => openPreview(item)}
                    className="px-4 py-2 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors text-sm font-medium"
                  >
                    📧 View Email
                  </button>
                  <button
                    onClick={() => handleApprove(item.id)}
                    disabled={actionLoading === item.id}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-green-300 transition-colors"
                  >
                    {actionLoading === item.id ? '...' : 'Approve'}
                  </button>
                  <button
                    onClick={() => handleReject(item.id)}
                    disabled={actionLoading === item.id}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-red-300 transition-colors"
                  >
                    {actionLoading === item.id ? '...' : 'Reject'}
                  </button>
                </div>
              </div>
            </div>
          ))}
          <div className="text-sm text-gray-500 text-center">
            Showing {items.length} of {total} items
          </div>
        </div>
      )}

      {/* Email Preview Modal */}
      {previewItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) closePreview(); }}
        >
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
            {/* Modal header */}
            <div className="flex items-start justify-between p-5 border-b border-gray-200">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-bold text-gray-900">{previewItem.brand_name}</span>
                  <span
                    className={`inline-flex px-2 py-0.5 text-xs font-semibold rounded-full ${
                      previewItem.is_sale ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {previewItem.is_sale ? 'Sale Detected' : 'No Sale'}
                  </span>
                  <span className="text-sm text-gray-500">
                    {Math.round(previewItem.confidence * 100)}% confidence
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-800 truncate">{previewItem.email_subject}</p>
                {previewItem.discount_summary && (
                  <p className="text-xs text-gray-500 mt-0.5">{previewItem.discount_summary}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">
                  Sent: {new Date(previewItem.sent_at).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={closePreview}
                className="ml-4 text-gray-400 hover:text-gray-600 text-2xl leading-none flex-shrink-0"
              >
                ×
              </button>
            </div>

            {/* Email content */}
            <div className="flex-1 overflow-hidden">
              {previewLoading ? (
                <div className="flex items-center justify-center h-64 text-gray-400">
                  Loading email...
                </div>
              ) : emailDetail?.html_content ? (
                <iframe
                  srcDoc={emailDetail.html_content}
                  sandbox="allow-same-origin"
                  className="w-full h-full border-0"
                  style={{ minHeight: '55vh' }}
                  title="Email preview"
                />
              ) : (
                <div className="p-6 text-gray-500 text-sm">
                  Email content not available.
                </div>
              )}
            </div>

            {/* Modal footer — approve / reject */}
            <div className="flex justify-end gap-3 p-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
              <button
                onClick={closePreview}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => handleReject(previewItem.id)}
                disabled={actionLoading === previewItem.id}
                className="px-5 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:bg-red-300 transition-colors font-medium"
              >
                {actionLoading === previewItem.id ? '...' : 'Reject'}
              </button>
              <button
                onClick={() => handleApprove(previewItem.id)}
                disabled={actionLoading === previewItem.id}
                className="px-5 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:bg-green-300 transition-colors font-medium"
              >
                {actionLoading === previewItem.id ? '...' : 'Approve'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
