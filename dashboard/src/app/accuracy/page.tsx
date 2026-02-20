export default function AccuracyPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Accuracy</h1>
      <p className="mt-2 text-gray-600">
        Track prediction accuracy and view adjustment suggestions.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Overall Hit Rate</h3>
          <p className="mt-2 text-3xl font-bold">--%</p>
        </div>
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Avg Timing Delta</h3>
          <p className="mt-2 text-3xl font-bold">-- days</p>
        </div>
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Total Predictions</h3>
          <p className="mt-2 text-3xl font-bold">0</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-semibold">Per-Brand Accuracy</h2>
        <div className="mt-4 rounded-lg border">
          <div className="p-8 text-center text-gray-500">
            No accuracy data yet. Predictions need to be verified first.
          </div>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-semibold">Adjustment Suggestions</h2>
        <div className="mt-4 rounded-lg border">
          <div className="p-8 text-center text-gray-500">
            No suggestions at this time.
          </div>
        </div>
      </div>
    </div>
  );
}
