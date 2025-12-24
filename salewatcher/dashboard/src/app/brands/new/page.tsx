'use client';

import { useState } from 'react';
import Link from 'next/link';
import { brandsApi } from '@/lib/api';

export default function NewBrandPage() {
  const [name, setName] = useState('');
  const [milledSlug, setMilledSlug] = useState('');
  const [excludedCategories, setExcludedCategories] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Parse excluded categories
      const categories = excludedCategories
        .split(',')
        .map((c) => c.trim())
        .filter((c) => c.length > 0);

      await brandsApi.create({
        name,
        milled_slug: milledSlug,
        excluded_categories: categories,
      });

      setSuccess(true);
      // Redirect after success
      setTimeout(() => {
        window.location.href = '/brands';
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create brand');
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate slug from name
  const handleNameChange = (value: string) => {
    setName(value);
    if (!milledSlug || milledSlug === name.toLowerCase().replace(/[^a-z0-9]+/g, '-')) {
      setMilledSlug(value.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
    }
  };

  if (success) {
    return (
      <div className="max-w-md mx-auto mt-8">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <div className="text-green-500 text-4xl mb-4">✓</div>
          <h2 className="text-lg font-semibold text-green-800">Brand Created!</h2>
          <p className="text-green-600 mt-2">Redirecting to brands list...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto">
      <div className="mb-6">
        <Link href="/brands" className="text-blue-600 hover:text-blue-800">
          ← Back to Brands
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-xl font-bold text-gray-900 mb-6">Add New Brand</h1>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              Brand Name *
            </label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="e.g., Target"
            />
          </div>

          <div>
            <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-1">
              Milled.com Slug *
            </label>
            <input
              type="text"
              id="slug"
              value={milledSlug}
              onChange={(e) => setMilledSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              required
              pattern="[a-z0-9-]+"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="e.g., target"
            />
            <p className="text-xs text-gray-500 mt-1">
              The slug used in milled.com/stores/{milledSlug || 'slug'}
            </p>
          </div>

          <div>
            <label htmlFor="categories" className="block text-sm font-medium text-gray-700 mb-1">
              Excluded Categories (optional)
            </label>
            <input
              type="text"
              id="categories"
              value={excludedCategories}
              onChange={(e) => setExcludedCategories(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="e.g., Clothing, Shoes, Groceries"
            />
            <p className="text-xs text-gray-500 mt-1">
              Comma-separated list of categories to ignore during extraction
            </p>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
            >
              {loading ? 'Creating...' : 'Create Brand'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
