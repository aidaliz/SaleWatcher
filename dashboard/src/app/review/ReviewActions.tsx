'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { reviewApi } from '@/lib/api';

interface ReviewActionsProps {
  reviewId: string;
}

export default function ReviewActions({ reviewId }: ReviewActionsProps) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  async function handleApprove() {
    setIsLoading(true);
    try {
      await reviewApi.approve(reviewId);
      router.refresh();
    } catch (error) {
      console.error('Failed to approve:', error);
      alert('Failed to approve extraction');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleReject() {
    setIsLoading(true);
    try {
      await reviewApi.reject(reviewId);
      router.refresh();
    } catch (error) {
      console.error('Failed to reject:', error);
      alert('Failed to reject extraction');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={handleReject}
        disabled={isLoading}
        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        Reject
      </button>
      <button
        onClick={handleApprove}
        disabled={isLoading}
        className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
      >
        {isLoading ? 'Processing...' : 'Approve'}
      </button>
    </>
  );
}
