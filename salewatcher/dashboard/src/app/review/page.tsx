'use client';

import { useEffect, useState } from 'react';
import { reviewApi, ReviewItem } from '@/lib/api';

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchReviewItems();
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

  const handleApprove = async (id: string) => {
    setActionLoading(id);
    try {
      await reviewApi.approve(id);
      setItems(items.filter((item) => item.id !== id));
      setTotal(total - 1);
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
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
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
                <div className="flex gap-2 ml-4">
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
    </div>
  );
}
