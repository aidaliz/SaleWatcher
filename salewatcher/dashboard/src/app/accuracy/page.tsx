'use client';

import { useEffect, useState } from 'react';
import { accuracyApi, AccuracyStats, BrandAccuracy } from '@/lib/api';

export default function AccuracyPage() {
  const [stats, setStats] = useState<AccuracyStats | null>(null);
  const [brandStats, setBrandStats] = useState<BrandAccuracy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAccuracy() {
      try {
        setLoading(true);
        setError(null);
        const [overallData, brandsData] = await Promise.all([
          accuracyApi.overall(),
          accuracyApi.brands(),
        ]);
        setStats(overallData);
        setBrandStats(brandsData.brands);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load accuracy data');
      } finally {
        setLoading(false);
      }
    }

    fetchAccuracy();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading accuracy data...</div>
      </div>
    );
  }

  const getTierColor = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'high':
        return 'bg-green-100 text-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'low':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Prediction Accuracy</h1>

      {error && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
          {error}
        </div>
      )}

      {/* Overall Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-blue-600">
              {(stats.hit_rate * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-500">Overall Hit Rate</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-green-600">{stats.hits}</div>
            <div className="text-sm text-gray-500">Hits</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-red-600">{stats.misses}</div>
            <div className="text-sm text-gray-500">Misses</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-3xl font-bold text-gray-600">{stats.pending}</div>
            <div className="text-sm text-gray-500">Pending Verification</div>
          </div>
        </div>
      )}

      {/* Per-Brand Stats */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Accuracy by Brand</h2>
        </div>

        {brandStats.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No brand accuracy data available yet. Predictions need to be verified first.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Brand
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hit Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hits / Misses
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reliability
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {brandStats.map((brand) => (
                <tr key={brand.brand_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="font-medium text-gray-900">{brand.brand_name}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-20 bg-gray-200 rounded-full h-2 mr-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{ width: `${brand.hit_rate * 100}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-600">
                        {(brand.hit_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className="text-green-600">{brand.hits}</span>
                    {' / '}
                    <span className="text-red-600">{brand.misses}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {brand.total_predictions}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTierColor(brand.reliability_tier)}`}
                    >
                      {brand.reliability_tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
