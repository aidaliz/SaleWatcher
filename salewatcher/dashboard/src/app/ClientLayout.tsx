'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

const navItems = [
  { href: '/', label: 'Overview', icon: '📊' },
  { href: '/brands', label: 'Brands', icon: '🏷️' },
  { href: '/scrape', label: 'Scrape Emails', icon: '📧' },
  { href: '/emails', label: 'View Emails', icon: '📬' },
  { href: '/predictions', label: 'Predictions', icon: '🔮' },
  { href: '/review', label: 'Review Queue', icon: '📋' },
  { href: '/accuracy', label: 'Accuracy', icon: '🎯' },
];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // Close sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  // Close sidebar on ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex min-h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 w-64 bg-gray-900 text-white z-40 transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}
      >
        <div className="p-5 flex items-center justify-between border-b border-gray-800">
          <div>
            <h1 className="text-xl font-bold">SaleWatcher</h1>
            <p className="text-xs text-gray-400">Sales Prediction System</p>
          </div>
          <button
            className="lg:hidden text-gray-400 hover:text-white p-1 rounded"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <nav className="mt-2 pb-4">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors
                ${pathname === item.href ? 'bg-gray-800 text-white border-r-2 border-blue-400' : ''}`}
            >
              <span className="mr-3 text-lg">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* Right side: top bar + main content */}
      <div className="flex-1 flex flex-col lg:ml-64">
        {/* Mobile top bar */}
        <header className="lg:hidden sticky top-0 z-20 bg-gray-900 text-white flex items-center px-4 py-3 shadow-md">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-300 hover:text-white mr-4 p-1"
            aria-label="Open menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="font-bold text-lg">SaleWatcher</span>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
