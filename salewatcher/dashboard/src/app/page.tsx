'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { brandsApi, predictionsApi, reviewApi, accuracyApi, Prediction, AccuracyStats } from '@/lib/api';

interface DashboardStats {
  upcomingPredictions: number;
  reviewQueue: number;
  activeBrands: number;
  hitRate: number;
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats>({
    upcomingPredictions: 0,
    reviewQueue: 0,
    activeBrands: 0,
    hitRate: 0,
  });
  const [recentPredictions, setRecentPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch all data in parallel
        const [brandsData, upcomingData, reviewData, accuracyData] = await Promise.all([
          brandsApi.list({ limit: 100 }).catch(() => ({ brands: [], total: 0 })),
          predictionsApi.upcoming(7).catch(() => ({ predictions: [], total: 0 })),
          reviewApi.list({ limit: 1 }).catch(() => ({ items: [], total: 0 })),
          accuracyApi.overall().catch(() => ({ hit_rate: 0 } as AccuracyStats)),
        ]);

        setStats({
          upcomingPredictions: upcomingData.total,
          reviewQueue: reviewData.total,
          activeBrands: brandsData.total,
          hitRate: accuracyData.hit_rate * 100,
        });

        setRecentPredictions(upcomingData.predictions.slice(0, 5));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  const statCards = [
    { label: 'Upcoming Predictions', value: stats.upcomingPredictions, href: '/predictions', color: 'bg-blue-500' },
    { label: 'Review Queue', value: stats.reviewQueue, href: '/review', color: 'bg-yellow-500' },
    { label: 'Active Brands', value: stats.activeBrands, href: '/brands', color: 'bg-green-500' },
    { label: 'Hit Rate', value: `${stats.hitRate.toFixed(1)}%`, href: '/accuracy', color: 'bg-purple-500' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard Overview</h1>

      {error && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
          Note: Some data could not be loaded. The backend API may not be running.
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat) => (
          <Link key={stat.label} href={stat.href}>
            <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer">
              <div className={`w-12 h-12 ${stat.color} rounded-lg flex items-center justify-center text-white text-xl mb-4`}>
                {typeof stat.value === 'number' ? stat.value : '%'}
              </div>
              <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
              <div className="text-sm text-gray-500">{stat.label}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Recent Predictions */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Upcoming Predictions</h2>
        </div>
        <div className="p-6">
          {recentPredictions.length === 0 ? (
            <p className="text-gray-500 text-center py-4">
              No upcoming predictions. Add brands and run the prediction engine to see results.
            </p>
          ) : (
            <div className="space-y-4">
              {recentPredictions.map((prediction) => (
                <div key={prediction.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <div className="font-medium text-gray-900">
                      {prediction.brand?.name || 'Unknown Brand'}
                    </div>
                    <div className="text-sm text-gray-500">
                      {prediction.discount_summary}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-gray-900">
                      {new Date(prediction.predicted_start).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      {Math.round(prediction.confidence * 100)}% confidence
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
