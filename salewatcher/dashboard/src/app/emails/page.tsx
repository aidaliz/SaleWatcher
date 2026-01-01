'use client';

import { useEffect, useState } from 'react';
import { emailsApi, brandsApi, Email, EmailStats, Brand } from '@/lib/api';

export default function EmailsPage() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedBrand, setSelectedBrand] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<'gmail' | 'milled' | ''>('');
  const [selectedExtracted, setSelectedExtracted] = useState<string>('');
  const [selectedIsSale, setSelectedIsSale] = useState<string>('');

  // Pagination
  const [page, setPage] = useState(0);
  const limit = 50;

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [emailsData, statsData, brandsData] = await Promise.all([
        emailsApi.list({
          skip: page * limit,
          limit,
          brand_id: selectedBrand || undefined,
          source: selectedSource || undefined,
          extracted: selectedExtracted === '' ? undefined : selectedExtracted === 'true',
          is_sale: selectedIsSale === '' ? undefined : selectedIsSale === 'true',
        }),
        emailsApi.stats(),
        brandsApi.list({ limit: 100 }),
      ]);

      setEmails(emailsData.emails);
      setTotal(emailsData.total);
      setStats(statsData);
      setBrands(brandsData.brands);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, selectedBrand, selectedSource, selectedExtracted, selectedIsSale]);

  const resetFilters = () => {
    setSelectedBrand('');
    setSelectedSource('');
    setSelectedExtracted('');
    setSelectedIsSale('');
    setPage(0);
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Emails & Extractions</h1>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800">x</button>
        </div>
      )}

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-900">{stats.total_emails}</div>
            <div className="text-sm text-gray-500">Total Emails</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">{stats.gmail_emails}</div>
            <div className="text-sm text-gray-500">From Gmail</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-blue-600">{stats.milled_emails}</div>
            <div className="text-sm text-gray-500">From Milled</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-purple-600">{stats.extracted}</div>
            <div className="text-sm text-gray-500">Extracted</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-400">{stats.not_extracted}</div>
            <div className="text-sm text-gray-500">Not Extracted</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-emerald-600">{stats.sales_found}</div>
            <div className="text-sm text-gray-500">Sales Found</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-400">{stats.non_sales}</div>
            <div className="text-sm text-gray-500">Non-Sales</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-yellow-600">{stats.pending_review}</div>
            <div className="text-sm text-gray-500">Pending Review</div>
          </div>
        </div>
      )}

      {/* Brand Stats */}
      {stats && stats.by_brand.length > 0 && (
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Emails by Brand</h2>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {stats.by_brand.map((brand) => (
                <div
                  key={brand.brand_id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                  onClick={() => {
                    setSelectedBrand(brand.brand_id);
                    setPage(0);
                  }}
                >
                  <div className="font-medium text-gray-900">{brand.brand_name}</div>
                  <div className="flex gap-4 mt-2 text-sm">
                    <span className="text-gray-600">Total: {brand.total}</span>
                    <span className="text-green-600">Gmail: {brand.gmail}</span>
                    <span className="text-blue-600">Milled: {brand.milled}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Brand</label>
            <select
              value={selectedBrand}
              onChange={(e) => { setSelectedBrand(e.target.value); setPage(0); }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Brands</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>{brand.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
            <select
              value={selectedSource}
              onChange={(e) => { setSelectedSource(e.target.value as any); setPage(0); }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Sources</option>
              <option value="gmail">Gmail</option>
              <option value="milled">Milled.com</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Extracted</label>
            <select
              value={selectedExtracted}
              onChange={(e) => { setSelectedExtracted(e.target.value); setPage(0); }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All</option>
              <option value="true">Extracted</option>
              <option value="false">Not Extracted</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Is Sale?</label>
            <select
              value={selectedIsSale}
              onChange={(e) => { setSelectedIsSale(e.target.value); setPage(0); }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All</option>
              <option value="true">Sales Only</option>
              <option value="false">Non-Sales Only</option>
            </select>
          </div>
          <button
            onClick={resetFilters}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
          >
            Reset Filters
          </button>
        </div>
      </div>

      {/* Email List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">
            Emails ({total.toLocaleString()} total)
          </h2>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Prev
              </button>
              <span className="text-sm text-gray-600">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : emails.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No emails found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Brand</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subject</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sent</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sale Info</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {emails.map((email) => (
                  <tr key={email.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        email.source === 'gmail'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        {email.source === 'gmail' ? 'Gmail' : 'Milled'}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      {email.brand_name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 max-w-md truncate" title={email.subject}>
                      {email.subject}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {new Date(email.sent_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {!email.is_extracted ? (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">
                          Not Extracted
                        </span>
                      ) : email.is_sale ? (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800">
                          Sale Found
                        </span>
                      ) : (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">
                          No Sale
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                      {email.discount_summary || '-'}
                      {email.confidence !== null && (
                        <span className="ml-2 text-xs text-gray-400">
                          ({Math.round(email.confidence * 100)}%)
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
