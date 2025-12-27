import { predictionsApi, Prediction } from '@/lib/api';

async function getPredictions(): Promise<{ predictions: Prediction[]; total: number }> {
  try {
    return await predictionsApi.upcoming(30);
  } catch (error) {
    console.error('Failed to fetch predictions:', error);
    return { predictions: [], total: 0 };
  }
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  let colorClass = 'bg-gray-100 text-gray-700';
  if (confidence >= 0.8) {
    colorClass = 'bg-green-100 text-green-700';
  } else if (confidence >= 0.6) {
    colorClass = 'bg-yellow-100 text-yellow-700';
  } else {
    colorClass = 'bg-red-100 text-red-700';
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${colorClass}`}>
      {pct}%
    </span>
  );
}

function formatDateRange(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);

  const startMonth = startDate.toLocaleDateString('en-US', { month: 'short' });
  const startDay = startDate.getDate();
  const endMonth = endDate.toLocaleDateString('en-US', { month: 'short' });
  const endDay = endDate.getDate();

  if (startMonth === endMonth) {
    return `${startMonth} ${startDay}-${endDay}`;
  }
  return `${startMonth} ${startDay} - ${endMonth} ${endDay}`;
}

function getDaysUntil(dateStr: string): number {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = date.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function DaysUntilBadge({ dateStr }: { dateStr: string }) {
  const days = getDaysUntil(dateStr);

  if (days < 0) {
    return (
      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">
        Ended
      </span>
    );
  }

  if (days === 0) {
    return (
      <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
        Today!
      </span>
    );
  }

  if (days <= 3) {
    return (
      <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-orange-700">
        {days} day{days !== 1 ? 's' : ''}
      </span>
    );
  }

  if (days <= 7) {
    return (
      <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-1 text-xs font-medium text-yellow-700">
        {days} days
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">
      {days} days
    </span>
  );
}

export default async function PredictionsPage() {
  const { predictions, total } = await getPredictions();

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Predictions</h1>
          <p className="mt-1 text-sm text-gray-600">
            {total} upcoming prediction{total !== 1 ? 's' : ''} in the next 30 days
          </p>
        </div>
      </div>

      <p className="mt-2 text-gray-600">
        Sales predicted based on historical patterns from last year.
      </p>

      {predictions.length === 0 ? (
        <div className="mt-6 rounded-lg border border-dashed p-8 text-center">
          <h3 className="text-lg font-medium text-gray-900">No upcoming predictions</h3>
          <p className="mt-1 text-sm text-gray-500">
            Predictions will appear here once historical data is analyzed.
          </p>
        </div>
      ) : (
        <div className="mt-6 overflow-hidden rounded-lg border">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Brand
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Predicted Discount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Expected Dates
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Starts In
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Calendar
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {predictions.map((prediction) => (
                <tr key={prediction.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="font-medium text-gray-900">
                      {prediction.brand?.name || 'Unknown Brand'}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-gray-900">
                      {prediction.discount_summary || 'Sale'}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="text-gray-900">
                      {formatDateRange(prediction.predicted_start, prediction.predicted_end)}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <DaysUntilBadge dateStr={prediction.predicted_start} />
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <ConfidenceBadge confidence={prediction.confidence} />
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    {prediction.calendar_event_id ? (
                      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
                        Synced
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-500">
                        Not synced
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
  );
}
