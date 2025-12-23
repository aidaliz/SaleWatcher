export default function BrandsPage() {
  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Brands</h1>
        <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          Add Brand
        </button>
      </div>
      <p className="mt-2 text-gray-600">
        Manage the retail brands you're tracking for sales predictions.
      </p>

      <div className="mt-6 rounded-lg border">
        <div className="p-8 text-center text-gray-500">
          No brands configured yet. Click "Add Brand" to get started.
        </div>
      </div>
    </div>
  );
}
