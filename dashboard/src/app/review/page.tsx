export default function ReviewPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Review Queue</h1>
      <p className="mt-2 text-gray-600">
        Approve or reject borderline sale extractions that need human review.
      </p>

      <div className="mt-6 rounded-lg border">
        <div className="p-8 text-center text-gray-500">
          No items pending review.
        </div>
      </div>
    </div>
  );
}
