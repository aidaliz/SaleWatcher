export default function PredictionsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Predictions</h1>
      <p className="mt-2 text-gray-600">
        View all predicted sales based on historical patterns.
      </p>

      <div className="mt-4 flex gap-4">
        <select className="rounded-lg border px-3 py-2 text-sm">
          <option value="">All Brands</option>
        </select>
        <select className="rounded-lg border px-3 py-2 text-sm">
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
          <option value="all">All</option>
        </select>
      </div>

      <div className="mt-6 rounded-lg border">
        <div className="p-8 text-center text-gray-500">
          No predictions yet. Run a historical backfill to generate predictions.
        </div>
      </div>
    </div>
  );
}
