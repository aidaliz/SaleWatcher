'use client';

import { useEffect, useState } from 'react';
import { brandsApi, scrapeApi, gmailApi, Brand, ScrapeJob, BrandStats, GmailStatus } from '@/lib/api';

export default function ScrapePage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandStats, setBrandStats] = useState<Record<string, BrandStats>>({});
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [scrapingBrand, setScrapingBrand] = useState<string | null>(null);
  const [syncingBrand, setSyncingBrand] = useState<string | null>(null);

  // Gmail status
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [gmailLoading, setGmailLoading] = useState(false);

  // Gmail configuration
  const [showGmailConfig, setShowGmailConfig] = useState(false);
  const [gmailClientId, setGmailClientId] = useState('');
  const [gmailClientSecret, setGmailClientSecret] = useState('');

  // Scrape settings
  const [daysBack, setDaysBack] = useState(365);
  const [maxEmails, setMaxEmails] = useState(500);
  const [runExtraction, setRunExtraction] = useState(true);
  const [runPredictions, setRunPredictions] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [brandsData, jobsData, gmailStatusData] = await Promise.all([
        brandsApi.list({ limit: 100 }),
        scrapeApi.listJobs().catch(() => []),
        gmailApi.getStatus().catch(() => null),
      ]);
      setBrands(brandsData.brands);
      setJobs(jobsData);
      setGmailStatus(gmailStatusData);

      // Fetch stats for each brand
      const statsPromises = brandsData.brands.map(async (brand) => {
        try {
          const stats = await scrapeApi.getBrandStats(brand.milled_slug);
          return { slug: brand.milled_slug, stats };
        } catch {
          return null;
        }
      });
      const statsResults = await Promise.all(statsPromises);
      const statsMap: Record<string, BrandStats> = {};
      statsResults.forEach((result) => {
        if (result) {
          statsMap[result.slug] = result.stats;
        }
      });
      setBrandStats(statsMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Poll for job updates
  useEffect(() => {
    const runningJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending');
    if (runningJobs.length === 0) return;

    const interval = setInterval(async () => {
      const updatedJobs = await scrapeApi.listJobs().catch(() => []);
      setJobs(updatedJobs);

      // Check if any running jobs completed
      const stillRunning = updatedJobs.filter((j) => j.status === 'running' || j.status === 'pending');
      if (stillRunning.length === 0) {
        // Refresh stats
        fetchData();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobs]);

  const handleScrape = async (brandSlug: string) => {
    try {
      setScrapingBrand(brandSlug);
      setError(null);
      const result = await scrapeApi.startScrape(brandSlug, {
        days_back: daysBack,
        max_emails: maxEmails,
        run_extraction: runExtraction,
        run_predictions: runPredictions,
      });
      // Refresh jobs list
      const updatedJobs = await scrapeApi.listJobs();
      setJobs(updatedJobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start scrape');
    } finally {
      setScrapingBrand(null);
    }
  };

  const handleGmailSync = async (brandId: string, brandName: string) => {
    try {
      setSyncingBrand(brandId);
      setError(null);
      setSuccess(null);
      const result = await gmailApi.syncBrand(brandId, daysBack, maxEmails);
      setSuccess(`Gmail sync for ${brandName}: ${result.message}`);
      // Refresh stats
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync Gmail');
    } finally {
      setSyncingBrand(null);
    }
  };

  const handleGmailSyncAll = async () => {
    try {
      setGmailLoading(true);
      setError(null);
      setSuccess(null);
      const result = await gmailApi.syncAll(daysBack, maxEmails);
      setSuccess(result.message);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync all brands from Gmail');
    } finally {
      setGmailLoading(false);
    }
  };

  const handleConnectGmail = async () => {
    try {
      setGmailLoading(true);
      setError(null);
      const result = await gmailApi.startAuth();
      // Redirect to Google OAuth
      window.location.href = result.auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Gmail auth');
      setGmailLoading(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!confirm('Are you sure you want to disconnect Gmail?')) return;
    try {
      setGmailLoading(true);
      await gmailApi.disconnect();
      setGmailStatus({ configured: true, authenticated: false, message: 'Gmail disconnected' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Gmail');
    } finally {
      setGmailLoading(false);
    }
  };

  const handleConfigureGmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gmailClientId || !gmailClientSecret) {
      setError('Please enter both Client ID and Client Secret');
      return;
    }
    try {
      setGmailLoading(true);
      setError(null);
      const result = await gmailApi.configure(gmailClientId, gmailClientSecret);
      setSuccess(result.message);
      setShowGmailConfig(false);
      setGmailClientId('');
      setGmailClientSecret('');
      // Refresh Gmail status
      const status = await gmailApi.getStatus();
      setGmailStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to configure Gmail');
    } finally {
      setGmailLoading(false);
    }
  };

  const getStatusBadge = (status: ScrapeJob['status']) => {
    const styles = {
      pending: 'bg-gray-100 text-gray-800',
      running: 'bg-blue-100 text-blue-800 animate-pulse',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${styles[status]}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Email Sources</h1>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-600 hover:text-red-800">×</button>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg text-green-800">
          {success}
          <button onClick={() => setSuccess(null)} className="ml-2 text-green-600 hover:text-green-800">×</button>
        </div>
      )}

      {/* Gmail Connection Status */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              Gmail Integration
              {gmailStatus?.authenticated ? (
                <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                  Connected
                </span>
              ) : gmailStatus?.configured ? (
                <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">
                  Not Connected
                </span>
              ) : (
                <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">
                  Not Configured
                </span>
              )}
            </h2>
            <p className="text-sm text-gray-500 mt-1">{gmailStatus?.message}</p>
          </div>
          <div className="flex gap-2">
            {gmailStatus?.authenticated ? (
              <>
                <button
                  onClick={handleGmailSyncAll}
                  disabled={gmailLoading}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300"
                >
                  {gmailLoading ? 'Syncing...' : 'Sync All Brands'}
                </button>
                <button
                  onClick={handleDisconnectGmail}
                  disabled={gmailLoading}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:bg-gray-100"
                >
                  Disconnect
                </button>
              </>
            ) : gmailStatus?.configured ? (
              <button
                onClick={handleConnectGmail}
                disabled={gmailLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
              >
                {gmailLoading ? 'Connecting...' : 'Connect Gmail'}
              </button>
            ) : (
              <button
                onClick={() => setShowGmailConfig(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Configure Gmail
              </button>
            )}
          </div>
        </div>

        {/* Gmail Configuration Form */}
        {showGmailConfig && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-md font-medium text-gray-900 mb-3">Configure Gmail OAuth Credentials</h3>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-800 mb-2">
                <strong>To get Gmail OAuth credentials:</strong>
              </p>
              <ol className="text-sm text-blue-700 list-decimal list-inside space-y-1">
                <li>Go to the <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="underline">Google Cloud Console</a></li>
                <li>Create a new project or select an existing one</li>
                <li>Enable the Gmail API</li>
                <li>Create OAuth 2.0 credentials (Web application type)</li>
                <li>Add <code className="bg-blue-100 px-1 rounded">http://localhost:8000/api/email/oauth/callback</code> as an authorized redirect URI</li>
                <li>Copy the Client ID and Client Secret below</li>
              </ol>
            </div>
            <form onSubmit={handleConfigureGmail} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
                <input
                  type="text"
                  value={gmailClientId}
                  onChange={(e) => setGmailClientId(e.target.value)}
                  placeholder="your-client-id.apps.googleusercontent.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client Secret</label>
                <input
                  type="password"
                  value={gmailClientSecret}
                  onChange={(e) => setGmailClientSecret(e.target.value)}
                  placeholder="GOCSPX-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={gmailLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
                >
                  {gmailLoading ? 'Saving...' : 'Save Credentials'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowGmailConfig(false)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Settings Panel */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Sync Settings</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Days Back</label>
            <input
              type="number"
              value={daysBack}
              onChange={(e) => setDaysBack(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              min={1}
              max={730}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Emails</label>
            <input
              type="number"
              value={maxEmails}
              onChange={(e) => setMaxEmails(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              min={1}
              max={1000}
            />
          </div>
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={runExtraction}
                onChange={(e) => setRunExtraction(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">Run Extraction</span>
            </label>
          </div>
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={runPredictions}
                onChange={(e) => setRunPredictions(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">Generate Predictions</span>
            </label>
          </div>
        </div>
      </div>

      {/* Active Jobs */}
      {jobs.filter((j) => j.status === 'running' || j.status === 'pending').length > 0 && (
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Active Jobs</h2>
          </div>
          <div className="p-4">
            {jobs
              .filter((j) => j.status === 'running' || j.status === 'pending')
              .map((job) => (
                <div key={job.id} className="flex items-center justify-between p-4 bg-blue-50 rounded-lg mb-2">
                  <div>
                    <div className="font-medium text-gray-900">{job.brand_name}</div>
                    <div className="text-sm text-blue-600">{job.current_step}</div>
                  </div>
                  <div className="text-right">
                    {getStatusBadge(job.status)}
                    <div className="text-xs text-gray-500 mt-1">
                      {job.emails_scraped} scraped, {job.emails_extracted} extracted
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Brands List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Brands</h2>
          <p className="text-sm text-gray-500">Scrape from Milled.com or sync from Gmail</p>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Brand
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Emails
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Extracted
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Predictions
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {brands.map((brand) => {
              const stats = brandStats[brand.milled_slug];
              const isRunning = jobs.some(
                (j) => j.brand_id === brand.id && (j.status === 'running' || j.status === 'pending')
              );
              const isSyncing = syncingBrand === brand.id;

              return (
                <tr key={brand.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="font-medium text-gray-900">{brand.name}</div>
                    <div className="text-sm text-gray-500">{brand.milled_slug}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {stats?.total_emails ?? '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {stats?.extracted_sales ?? '-'}
                    {stats?.pending_review ? (
                      <span className="ml-1 text-yellow-600">({stats.pending_review} pending)</span>
                    ) : null}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {stats?.predictions ?? '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                    <button
                      onClick={() => handleScrape(brand.milled_slug)}
                      disabled={isRunning || scrapingBrand === brand.milled_slug}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                        isRunning || scrapingBrand === brand.milled_slug
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                      title="Scrape from Milled.com"
                    >
                      {isRunning ? 'Running...' : scrapingBrand === brand.milled_slug ? 'Starting...' : 'Milled'}
                    </button>
                    {gmailStatus?.authenticated && (
                      <button
                        onClick={() => handleGmailSync(brand.id, brand.name)}
                        disabled={isSyncing}
                        className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                          isSyncing
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-green-600 text-white hover:bg-green-700'
                        }`}
                        title="Sync from Gmail"
                      >
                        {isSyncing ? 'Syncing...' : 'Gmail'}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Recent Jobs History */}
      {jobs.filter((j) => j.status === 'completed' || j.status === 'failed').length > 0 && (
        <div className="bg-white rounded-lg shadow mt-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Milled Jobs</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {jobs
              .filter((j) => j.status === 'completed' || j.status === 'failed')
              .slice(0, 5)
              .map((job) => (
                <div key={job.id} className="px-6 py-4 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-900">{job.brand_name}</div>
                    <div className="text-sm text-gray-500">
                      {job.emails_scraped} scraped, {job.emails_extracted} extracted, {job.predictions_generated}{' '}
                      predictions
                    </div>
                    {job.error && <div className="text-sm text-red-600 mt-1">{job.error}</div>}
                  </div>
                  <div className="text-right">
                    {getStatusBadge(job.status)}
                    {job.completed_at && (
                      <div className="text-xs text-gray-500 mt-1">
                        {new Date(job.completed_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
