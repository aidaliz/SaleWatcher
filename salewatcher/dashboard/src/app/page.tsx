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

interface CalendarDay {
  date: Date;
  isCurrentMonth: boolean;
  predictions: Prediction[];
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats>({
    upcomingPredictions: 0,
    reviewQueue: 0,
    activeBrands: 0,
    hitRate: 0,
  });
  const [allPredictions, setAllPredictions] = useState<Prediction[]>([]);
  const [recentPredictions, setRecentPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentMonth, setCurrentMonth] = useState(new Date());

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch all data in parallel - get predictions for next 365 days
        const [brandsData, upcomingData, allPredictionsData, reviewData, accuracyData] = await Promise.all([
          brandsApi.list({ limit: 100 }).catch(() => ({ brands: [], total: 0 })),
          predictionsApi.upcoming(365).catch(() => ({ predictions: [], total: 0 })),
          predictionsApi.list({ limit: 200 }).catch(() => ({ predictions: [], total: 0 })),
          reviewApi.list({ limit: 1 }).catch(() => ({ items: [], total: 0 })),
          accuracyApi.overall().catch(() => ({ hit_rate: 0 } as AccuracyStats)),
        ]);

        setStats({
          upcomingPredictions: upcomingData.total,
          reviewQueue: reviewData.total,
          activeBrands: brandsData.total,
          hitRate: accuracyData.hit_rate * 100,
        });

        setAllPredictions(allPredictionsData.predictions);
        setRecentPredictions(upcomingData.predictions.slice(0, 5));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  // Calendar helper functions
  const getCalendarDays = (month: Date): CalendarDay[] => {
    const year = month.getFullYear();
    const monthIndex = month.getMonth();

    const firstDay = new Date(year, monthIndex, 1);
    const lastDay = new Date(year, monthIndex + 1, 0);

    const days: CalendarDay[] = [];

    // Add days from previous month to fill the first week
    const firstDayOfWeek = firstDay.getDay();
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      const date = new Date(year, monthIndex, -i);
      days.push({ date, isCurrentMonth: false, predictions: [] });
    }

    // Add days of current month
    for (let day = 1; day <= lastDay.getDate(); day++) {
      const date = new Date(year, monthIndex, day);
      const dayPredictions = allPredictions.filter(p => {
        const start = new Date(p.predicted_start);
        const end = new Date(p.predicted_end);
        return date >= new Date(start.getFullYear(), start.getMonth(), start.getDate()) &&
               date <= new Date(end.getFullYear(), end.getMonth(), end.getDate());
      });
      days.push({ date, isCurrentMonth: true, predictions: dayPredictions });
    }

    // Add days from next month to complete the grid
    const remainingDays = 42 - days.length; // 6 rows * 7 days
    for (let i = 1; i <= remainingDays; i++) {
      const date = new Date(year, monthIndex + 1, i);
      days.push({ date, isCurrentMonth: false, predictions: [] });
    }

    return days;
  };

  const navigateMonth = (direction: number) => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + direction, 1));
  };

  const calendarDays = getCalendarDays(currentMonth);

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

      {/* Calendar View */}
      <div className="bg-white rounded-lg shadow mb-8">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Sale Calendar</h2>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigateMonth(-1)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              &larr;
            </button>
            <span className="font-medium min-w-[150px] text-center">
              {currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </span>
            <button
              onClick={() => navigateMonth(1)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              &rarr;
            </button>
          </div>
        </div>
        <div className="p-4">
          {/* Day headers */}
          <div className="grid grid-cols-7 gap-1 mb-2">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
              <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">
                {day}
              </div>
            ))}
          </div>
          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, index) => (
              <div
                key={index}
                className={`min-h-[80px] p-1 border rounded-lg ${
                  day.isCurrentMonth ? 'bg-white' : 'bg-gray-50'
                } ${day.predictions.length > 0 ? 'border-blue-300' : 'border-gray-200'}`}
              >
                <div className={`text-sm ${day.isCurrentMonth ? 'text-gray-900' : 'text-gray-400'}`}>
                  {day.date.getDate()}
                </div>
                {day.predictions.length > 0 && (
                  <div className="mt-1 space-y-1">
                    {day.predictions.slice(0, 2).map((pred, i) => (
                      <div
                        key={i}
                        className="text-xs bg-blue-100 text-blue-800 px-1 py-0.5 rounded truncate"
                        title={`${pred.brand?.name}: ${pred.discount_summary}`}
                      >
                        {pred.brand?.name}
                      </div>
                    ))}
                    {day.predictions.length > 2 && (
                      <div className="text-xs text-gray-500">
                        +{day.predictions.length - 2} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Predictions List */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Upcoming Predictions</h2>
        </div>
        <div className="p-6">
          {recentPredictions.length === 0 ? (
            <p className="text-gray-500 text-center py-4">
              No upcoming predictions in the next year. Navigate the calendar above to see future predictions.
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
