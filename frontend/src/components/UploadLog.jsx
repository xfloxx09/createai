import { useState, useEffect, useCallback } from 'react'
import { getUploadLog } from '../api'

function StatusBadge({ status }) {
  if (status === 'success') return <span className="badge-success">Success</span>
  if (status === 'failed') return <span className="badge-fail">Failed</span>
  if (status === 'pending' || status === 'queued') return <span className="badge-pending">Pending</span>
  return <span className="badge-skip">Skipped</span>
}

function PlatformBadge({ platform }) {
  const colors = {
    instagram: 'bg-pink-900 text-pink-300',
    tiktok: 'bg-cyan-900 text-cyan-300',
    youtube: 'bg-red-900 text-red-300',
    facebook: 'bg-blue-900 text-blue-300',
  }
  return (
    <span className={`badge ${colors[platform] || 'bg-gray-700 text-gray-300'}`}>
      {platform}
    </span>
  )
}

export default function UploadLog() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const fetchLogs = useCallback(async () => {
    try {
      const data = await getUploadLog(100)
      setLogs(data)
    } catch (err) {
      console.error('Failed to fetch upload log:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  const filteredLogs = filter
    ? logs.filter((l) => l.platform === filter || l.status === filter)
    : logs

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Upload Log</h1>
        <button onClick={fetchLogs} className="btn-secondary text-sm">Refresh</button>
      </div>

      <div className="card">
        <div className="flex items-center gap-4 mb-4">
          <h2 className="text-lg font-semibold">Past Uploads</h2>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input text-sm"
          >
            <option value="">All</option>
            <optgroup label="Platforms">
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="youtube">YouTube</option>
              <option value="facebook">Facebook</option>
            </optgroup>
            <optgroup label="Status">
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
              <option value="skipped">Skipped</option>
            </optgroup>
          </select>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">Loading...</div>
        ) : filteredLogs.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            No uploads yet. Generate a video and upload it from the Generate tab.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-800">
                  <th className="pb-3 pr-4">Time</th>
                  <th className="pb-3 pr-4">Platform</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Caption</th>
                  <th className="pb-3 pr-4">Error</th>
                  <th className="pb-3 pr-4">Post URL</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-3 pr-4 text-gray-400 whitespace-nowrap text-xs">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                    </td>
                    <td className="py-3 pr-4">
                      <PlatformBadge platform={log.platform} />
                    </td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={log.status} />
                    </td>
                    <td className="py-3 pr-4 max-w-xs truncate text-gray-300">
                      {log.caption_snippet || log.hook_text || '-'}
                    </td>
                    <td className="py-3 pr-4 max-w-[200px] truncate text-red-400 text-xs">
                      {log.error_message || '-'}
                    </td>
                    <td className="py-3 pr-4">
                      {log.platform_post_url ? (
                        <a
                          href={log.platform_post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand-400 hover:text-brand-300 underline text-xs"
                        >
                          View Post
                        </a>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Upload Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          {['success', 'failed', 'pending', 'skipped'].map((status) => {
            const count = logs.filter((l) => l.status === status).length
            return (
              <div key={status} className="bg-gray-800 rounded-lg p-4">
                <div className={`text-2xl font-bold ${
                  status === 'success' ? 'text-green-400' :
                  status === 'failed' ? 'text-red-400' :
                  status === 'pending' ? 'text-yellow-400' :
                  'text-gray-400'
                }`}>
                  {count}
                </div>
                <div className="text-xs text-gray-400 mt-1 capitalize">{status}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
