'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { brandsApi, Brand } from '@/lib/api';

export default function BrandDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [brand, setBrand] = useState<Brand | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBrand() {
      try {
        const data = await brandsApi.get(id);
        setBrand(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load brand');
      } finally {
        setLoading(false);
      }
    }
    fetchBrand();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading brand...</div>
      </div>
    );
  }

  if (error || !brand) {
    return (
      <div>
        <Link href="/brands" className="text-sm text-blue-600 hover:text-blue-800">
          &larr; Back to Brands
        </Link>
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-600">
          {error || 'Brand not found'}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link href="/brands" className="text-sm text-blue-600 hover:text-blue-800">
          &larr; Back to Brands
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{brand.name}</h1>
        <Link
          href={`/brands/${brand.id}/edit`}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Edit Brand
        </Link>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border bg-white">
        <dl className="divide-y divide-gray-200">
          <div className="px-6 py-4 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Status</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              <span
                className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                  brand.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {brand.is_active ? 'Active' : 'Inactive'}
              </span>
            </dd>
          </div>
          <div className="px-6 py-4 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Milled.com Slug</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              <code className="rounded bg-gray-100 px-2 py-1">{brand.milled_slug}</code>
            </dd>
          </div>
          <div className="px-6 py-4 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Excluded Categories</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              {brand.excluded_categories && brand.excluded_categories.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {brand.excluded_categories.map((cat) => (
                    <span
                      key={cat}
                      className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-gray-400">None</span>
              )}
            </dd>
          </div>
          <div className="px-6 py-4 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Created</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              {new Date(brand.created_at).toLocaleString()}
            </dd>
          </div>
          <div className="px-6 py-4 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              {new Date(brand.updated_at).toLocaleString()}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
