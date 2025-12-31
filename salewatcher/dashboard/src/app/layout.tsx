import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'SaleWatcher Dashboard',
  description: 'Sales prediction dashboard for Amazon Online Arbitrage',
};

const navItems = [
  { href: '/', label: 'Overview', icon: '📊' },
  { href: '/brands', label: 'Brands', icon: '🏷️' },
  { href: '/scrape', label: 'Scrape Emails', icon: '📧' },
  { href: '/predictions', label: 'Predictions', icon: '🔮' },
  { href: '/review', label: 'Review Queue', icon: '📋' },
  { href: '/accuracy', label: 'Accuracy', icon: '🎯' },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <div className="flex">
          {/* Sidebar */}
          <aside className="fixed inset-y-0 left-0 w-64 bg-gray-900 text-white">
            <div className="p-6">
              <h1 className="text-xl font-bold">SaleWatcher</h1>
              <p className="text-sm text-gray-400">Sales Prediction System</p>
            </div>
            <nav className="mt-6">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center px-6 py-3 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
                >
                  <span className="mr-3">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>

          {/* Main content */}
          <main className="ml-64 flex-1 p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
