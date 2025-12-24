import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SaleWatcher Dashboard',
  description: 'Sales prediction dashboard for Amazon Online Arbitrage',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background antialiased">
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="relative w-64 border-r bg-gray-50 dark:bg-gray-900">
            <div className="p-4">
              <h1 className="text-xl font-bold">SaleWatcher</h1>
            </div>
            <nav className="mt-4 space-y-1 px-2">
              <a
                href="/"
                className="block rounded-lg px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Overview
              </a>
              <a
                href="/brands"
                className="block rounded-lg px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Brands
              </a>
              <a
                href="/review"
                className="block rounded-lg px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Review Queue
              </a>
              <a
                href="/predictions"
                className="block rounded-lg px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Predictions
              </a>
              <a
                href="/accuracy"
                className="block rounded-lg px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Accuracy
              </a>
            </nav>
            <div className="absolute bottom-4 left-4 right-4 text-xs text-gray-400">
              Build: v1.0.1 (Dec 24)
            </div>
          </aside>
          {/* Main content */}
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
