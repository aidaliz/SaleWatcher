'use client';

import { useEffect, useState } from 'react';
import {
  predictionsApi,
  brandsApi,
  Prediction,
  PredictionStats,
  Brand,
} from '@/lib/api';

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [stats, setStats] = useState<PredictionStats | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Generating state
  const [generating, setGenerating] = useState(false);

  // Filters
  const [selectedBrand, setSelectedBrand] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<string>('');

  // Pagination
  const [page, setPage] = useState(0);
  const limit = 50;

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear + i);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [predictionsData, statsData, brandsData] = await Promise.all([
        predictionsApi.list({
          skip: page * limit,
          limit,
          brand_id: selectedBrand || undefined,
          target_year: selectedYear ? parseInt(selectedYear) : undefined,
        }),
        predictionsApi.stats(),
        brandsApi.list({ limit: 100 }),
      ]);

      setPredictions(predictionsData.predictions);
      setTotal(predictionsData.total);
      setStats(statsData);
      setBrands(brandsData.brands);
    } catch (err: any) {
      const message = err?.message || (typeof err === 'string' ? err : JSON.stringify(err));
      setError(message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, selectedBrand, selectedYear]);

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      setError(null);
      setSuccess(null);

      const result = await predictionsApi.generate({
        brand_id: selectedBrand || undefined,
        years_ahead: 2,
      });

      setSuccess(result.message);
      fetchData();
    } catch (err: any) {
      const message = err?.message || (typeof err === 'string' ? err : JSON.stringify(err));
      setError(message || 'Failed to generate predictions');
    } finally {
      setGenerating(false);
    }
  };

  const resetFilters = () => {
    setSelectedBrand('');
    setSelectedYear('');
    setPage(0);
  };

  const totalPages = Math.ceil(total / limit);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Predictions</h1>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800">
            x
          </button>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg text-green-800">
          {success}
          <button onClick={() => setSuccess(null)} className="ml-2 text-green-600 hover:text-green-800">
            x
          </button>
        </div>
      )}

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-900">{stats.total_predictions}</div>
            <div className="text-sm text-gray-500">Total Predictions</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-blue-600">{stats.upcoming_predictions}</div>
            <div className="text-sm text-gray-500">Upcoming</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-gray-400">{stats.past_predictions}</div>
            <div className="text-sm text-gray-500">Past</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-purple-600">{stats.total_sale_windows}</div>
            <div className="text-sm text-gray-500">Sale Windows</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-emerald-600">{stats.total_extracted_sales}</div>
            <div className="text-sm text-gray-500">Tagged Sales</div>
          </div>
        </div>
      )}

      {/* Filters & Generate */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Brand</label>
            <select
              value={selectedBrand}
              onChange={(e) => {
                setSelectedBrand(e.target.value);
                setPage(0);
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Brands</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
            <select
              value={selectedYear}
              onChange={(e) => {
                setSelectedYear(e.target.value);
                setPage(0);
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Years</option>
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={resetFilters}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
          >
            Reset Filters
          </button>
        </div>

        {/* Generate Predictions */}
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-gray-200">
          <div className="text-sm text-gray-600">
            {stats
              ? `${stats.total_extracted_sales} tagged sales available for prediction generation`
              : 'Loading...'}
            {selectedBrand && ' (filtered by brand)'}
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className={`ml-auto px-4 py-2 rounded-lg font-medium ${
              generating
                ? 'bg-blue-200 text-blue-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {generating ? 'Generating...' : 'Generate Predictions'}
          </button>
        </div>
      </div>

      {/* Predictions List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">
            Predictions ({total.toLocaleString()} total)
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
        ) : predictions.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No predictions found.</p>
            <p className="mt-2 text-sm">
              Tag emails as sales, then click &quot;Generate Predictions&quot; to create predictions.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Brand
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Year
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Predicted Dates
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Discount
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Summary
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Confidence
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Calendar
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {predictions.map((prediction) => {
                  const isUpcoming = new Date(prediction.predicted_start) >= new Date();
                  return (
                    <tr key={prediction.id} className={`hover:bg-gray-50 ${!isUpcoming ? 'opacity-60' : ''}`}>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        {prediction.brand?.name || 'Unknown'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {prediction.target_year}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(prediction.predicted_start)} - {formatDate(prediction.predicted_end)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800">
                          {prediction.expected_discount}% {prediction.discount_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate" title={prediction.discount_summary}>
                        {prediction.discount_summary}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
                              style={{ width: `${prediction.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-gray-500">{Math.round(prediction.confidence * 100)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {prediction.synced_to_calendar ? (
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                            Synced
                          </span>
                        ) : (
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">
                            Not Synced
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
