'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { brandsApi, Brand } from '@/lib/api';

export default function EditBrandPage() {
  const params = useParams();
  const id = params.id as string;
  const [brand, setBrand] = useState<Brand | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    milled_slug: '',
    is_active: true,
    excluded_categories: '',
  });

  useEffect(() => {
    async function fetchBrand() {
      try {
        const data = await brandsApi.get(id);
        setBrand(data);
        setFormData({
          name: data.name,
          milled_slug: data.milled_slug,
          is_active: data.is_active,
          excluded_categories: data.excluded_categories?.join(', ') || '',
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load brand');
      } finally {
        setLoading(false);
      }
    }
    fetchBrand();
  }, [id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const excludedCategories = formData.excluded_categories
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      await brandsApi.update(id, {
        name: formData.name,
        milled_slug: formData.milled_slug,
        is_active: formData.is_active,
        excluded_categories: excludedCategories,
      });

      setSuccess(true);
      setTimeout(() => {
        window.location.href = '/brands';
      }, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update brand');
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading brand...</div>
      </div>
    );
  }

  if (error && !brand) {
    return (
      <div>
        <Link href="/brands" className="text-sm text-blue-600 hover:text-blue-800">
          &larr; Back to Brands
        </Link>
        <div className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-600">
          {error}
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

      <h1 className="text-2xl font-bold">Edit Brand</h1>
      <p className="mt-1 text-sm text-gray-600">Update brand settings</p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-lg space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-lg bg-green-50 p-4 text-sm text-green-600">
            Brand updated successfully! Redirecting...
          </div>
        )}

        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700">
            Brand Name
          </label>
          <input
            type="text"
            id="name"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label htmlFor="milled_slug" className="block text-sm font-medium text-gray-700">
            Milled.com Slug
          </label>
          <input
            type="text"
            id="milled_slug"
            required
            value={formData.milled_slug}
            onChange={(e) => setFormData({ ...formData, milled_slug: e.target.value })}
            className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            checked={formData.is_active}
            onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
            Active (track this brand)
          </label>
        </div>

        <div>
          <label htmlFor="excluded_categories" className="block text-sm font-medium text-gray-700">
            Excluded Categories
          </label>
          <input
            type="text"
            id="excluded_categories"
            value={formData.excluded_categories}
            onChange={(e) => setFormData({ ...formData, excluded_categories: e.target.value })}
            className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., Groceries, Beauty"
          />
          <p className="mt-1 text-xs text-gray-500">Comma-separated list</p>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
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
