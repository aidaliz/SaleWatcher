import { reviewApi, ExtractedSale } from '@/lib/api';
import ReviewActions from './ReviewActions';

async function getReviews(): Promise<{ reviews: ExtractedSale[]; total: number }> {
  try {
    return await reviewApi.list({ limit: 50 });
  } catch (error) {
    console.error('Failed to fetch reviews:', error);
    return { reviews: [], total: 0 };
  }
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  let colorClass = 'bg-red-100 text-red-700';
  if (confidence >= 0.7) {
    colorClass = 'bg-green-100 text-green-700';
  } else if (confidence >= 0.5) {
    colorClass = 'bg-yellow-100 text-yellow-700';
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${colorClass}`}>
      {pct}%
    </span>
  );
}

function formatDiscount(review: ExtractedSale): string {
  if (review.discount_type === 'percent_off' && review.discount_value) {
    return `${review.discount_value}% off`;
  }
  if (review.discount_type === 'bogo') {
    return 'Buy One Get One';
  }
  if (review.discount_type === 'free_shipping') {
    return 'Free Shipping';
  }
  if (review.raw_discount_text) {
    return review.raw_discount_text.slice(0, 50);
  }
  return review.discount_type;
}

export default async function ReviewPage() {
  const { reviews, total } = await getReviews();

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Review Queue</h1>
          <p className="mt-1 text-sm text-gray-600">
            {total} extraction{total !== 1 ? 's' : ''} pending review
          </p>
        </div>
      </div>

      <p className="mt-2 text-gray-600">
        These extractions have low confidence scores and need human verification.
      </p>

      {reviews.length === 0 ? (
        <div className="mt-6 rounded-lg border border-dashed p-8 text-center">
          <div className="text-4xl">✓</div>
          <h3 className="mt-2 text-lg font-medium text-gray-900">All caught up!</h3>
          <p className="mt-1 text-sm text-gray-500">
            No items pending review at the moment.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {reviews.map((review) => (
            <div
              key={review.id}
              className="overflow-hidden rounded-lg border bg-white shadow-sm"
            >
              <div className="border-b bg-gray-50 px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-gray-900">
                      {review.brand_name}
                    </span>
                    <span className="mx-2 text-gray-300">•</span>
                    <span className="text-sm text-gray-600">
                      {review.email_subject}
                    </span>
                  </div>
                  <ConfidenceBadge confidence={review.confidence} />
                </div>
              </div>

              <div className="p-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Extracted Discount</h4>
                    <p className="mt-1 text-lg font-semibold text-gray-900">
                      {formatDiscount(review)}
                    </p>
                    {review.discount_max && (
                      <p className="text-sm text-gray-500">
                        Up to {review.discount_max}%
                      </p>
                    )}
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Scope</h4>
                    <p className="mt-1 text-gray-900">
                      {review.is_sitewide ? (
                        <span className="inline-flex items-center rounded bg-blue-100 px-2 py-0.5 text-sm text-blue-700">
                          Sitewide
                        </span>
                      ) : (
                        <span className="text-sm text-gray-600">
                          {review.categories && review.categories.length > 0
                            ? review.categories.join(', ')
                            : 'Unknown categories'}
                        </span>
                      )}
                    </p>
                  </div>

                  {review.raw_discount_text && (
                    <div className="md:col-span-2">
                      <h4 className="text-sm font-medium text-gray-500">Raw Text</h4>
                      <p className="mt-1 rounded bg-gray-50 p-2 text-sm text-gray-700">
                        "{review.raw_discount_text}"
                      </p>
                    </div>
                  )}

                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Model Used</h4>
                    <p className="mt-1 text-sm text-gray-600">
                      {review.model_used || 'Unknown'}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex justify-end gap-2 border-t pt-4">
                  <ReviewActions reviewId={review.id} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
