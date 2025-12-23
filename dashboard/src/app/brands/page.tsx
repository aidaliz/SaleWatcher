import Link from 'next/link';
import { brandsApi, Brand } from '@/lib/api';

async function getBrands(): Promise<{ brands: Brand[]; total: number }> {
  try {
    return await brandsApi.list({ limit: 100 });
  } catch (error) {
    console.error('Failed to fetch brands:', error);
    return { brands: [], total: 0 };
  }
}

function BrandStatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
        isActive
          ? 'bg-green-100 text-green-700'
          : 'bg-gray-100 text-gray-600'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

export default async function BrandsPage() {
  const { brands, total } = await getBrands();

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Brands</h1>
          <p className="mt-1 text-sm text-gray-600">
            {total} brand{total !== 1 ? 's' : ''} being tracked
          </p>
        </div>
        <Link
          href="/brands/new"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Add Brand
        </Link>
      </div>

      {brands.length === 0 ? (
        <div className="mt-6 rounded-lg border border-dashed p-8 text-center">
          <h3 className="text-lg font-medium text-gray-900">No brands yet</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by adding a retail brand to track.
          </p>
          <Link
            href="/brands/new"
            className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Add your first brand
          </Link>
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
                  Milled Slug
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Exclusions
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {brands.map((brand) => (
                <tr key={brand.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="font-medium text-gray-900">{brand.name}</div>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <code className="rounded bg-gray-100 px-2 py-1 text-sm text-gray-700">
                      {brand.milled_slug}
                    </code>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <BrandStatusBadge isActive={brand.is_active} />
                  </td>
                  <td className="px-6 py-4">
                    {brand.excluded_categories && brand.excluded_categories.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {brand.excluded_categories.slice(0, 3).map((cat) => (
                          <span
                            key={cat}
                            className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                          >
                            {cat}
                          </span>
                        ))}
                        {brand.excluded_categories.length > 3 && (
                          <span className="text-xs text-gray-500">
                            +{brand.excluded_categories.length - 3} more
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-gray-400">None</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                    <Link
                      href={`/brands/${brand.id}`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      View
                    </Link>
                    <span className="mx-2 text-gray-300">|</span>
                    <Link
                      href={`/brands/${brand.id}/edit`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </Link>
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
