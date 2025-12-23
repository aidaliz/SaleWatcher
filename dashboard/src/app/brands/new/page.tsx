'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { brandsApi } from '@/lib/api';

export default function NewBrandPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    milled_slug: '',
    excluded_categories: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const excludedCategories = formData.excluded_categories
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      await brandsApi.create({
        name: formData.name,
        milled_slug: formData.milled_slug,
        excluded_categories: excludedCategories,
      });

      router.push('/brands');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create brand');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <Link
          href="/brands"
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          &larr; Back to Brands
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Add New Brand</h1>
      <p className="mt-1 text-sm text-gray-600">
        Add a retail brand to track on Milled.com
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-lg space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700"
          >
            Brand Name
          </label>
          <input
            type="text"
            id="name"
            required
            value={formData.name}
            onChange={(e) =>
              setFormData({ ...formData, name: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., Target"
          />
        </div>

        <div>
          <label
            htmlFor="milled_slug"
            className="block text-sm font-medium text-gray-700"
          >
            Milled.com Slug
          </label>
          <input
            type="text"
            id="milled_slug"
            required
            value={formData.milled_slug}
            onChange={(e) =>
              setFormData({ ...formData, milled_slug: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., target"
          />
          <p className="mt-1 text-xs text-gray-500">
            The brand identifier in Milled.com URLs (milled.com/stores/[slug])
          </p>
        </div>

        <div>
          <label
            htmlFor="excluded_categories"
            className="block text-sm font-medium text-gray-700"
          >
            Excluded Categories (optional)
          </label>
          <input
            type="text"
            id="excluded_categories"
            value={formData.excluded_categories}
            onChange={(e) =>
              setFormData({ ...formData, excluded_categories: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., Groceries, Beauty"
          />
          <p className="mt-1 text-xs text-gray-500">
            Comma-separated list of categories to ignore
          </p>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Brand'}
          </button>
          <Link
            href="/brands"
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
