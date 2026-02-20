export default function HomePage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Overview</h1>
      <p className="mt-2 text-gray-600">
        Welcome to SaleWatcher. View upcoming predictions and review queue status.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Stats cards */}
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Upcoming Predictions</h3>
          <p className="mt-2 text-3xl font-bold">0</p>
        </div>
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Review Queue</h3>
          <p className="mt-2 text-3xl font-bold">0</p>
        </div>
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Active Brands</h3>
          <p className="mt-2 text-3xl font-bold">0</p>
        </div>
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800">
          <h3 className="text-sm font-medium text-gray-500">Overall Hit Rate</h3>
          <p className="mt-2 text-3xl font-bold">--%</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-semibold">Recent Predictions</h2>
        <div className="mt-4 rounded-lg border">
          <div className="p-8 text-center text-gray-500">
            No predictions yet. Add brands and run a scrape to get started.
          </div>
        </div>
      </div>
    </div>
  );
}
