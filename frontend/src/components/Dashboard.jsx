import { useState, useEffect, useCallback, useRef } from 'react'
import { getScoredVideos, triggerScrape, getStats, getCostSummary, getStrategy, refreshStrategy } from '../api'
import Toast, { useToast } from './Toast'

const PLATFORMS = ['instagram', 'tiktok', 'youtube', 'facebook']
const STATUS_PHASES = [
  { min: 0, max: 10, text: 'Finding trending Shorts on YouTube...' },
  { min: 10, max: 20, text: 'Scanning TikTok for rising gems...' },
  { min: 20, max: 30, text: 'Checking Instagram Reels trends...' },
  { min: 30, max: 40, text: 'Looking at Facebook Reels...' },
  { min: 40, max: 55, text: 'Analyzing growth velocity & filtering gems...' },
  { min: 55, max: 999, text: 'Scoring & saving — almost there...' },
]

function ScrapeModal({ scraping }) {
  const [elapsed, setElapsed] = useState(0)
  const [show, setShow] = useState(false)
  const startRef = useRef(null)

  useEffect(() => {
    if (scraping) {
      setShow(true)
      startRef.current = Date.now()
      setElapsed(0)
      const id = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
      }, 500)
      return () => clearInterval(id)
    } else {
      const id = setTimeout(() => setShow(false), 400)
      return () => clearTimeout(id)
    }
  }, [scraping])

  if (!show) return null

  const phase = STATUS_PHASES.find(p => elapsed >= p.min && elapsed < p.max) || STATUS_PHASES[STATUS_PHASES.length - 1]

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-300 ${scraping ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
      <div className="absolute inset-0 bg-black/70" />
      <div className="relative bg-gray-900 border border-gray-700 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="flex flex-col items-center gap-5">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 border-4 border-brand-500/20 rounded-full" />
            <div className="absolute inset-0 border-4 border-transparent border-t-brand-500 rounded-full animate-spin" />
          </div>
          <div className="text-center">
            <p className="text-lg font-semibold text-white">Scraping Viral Gems</p>
            <p className="text-sm text-gray-400 mt-2 min-h-[20px] transition-all">{phase.text}</p>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-brand-500 to-green-500 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, (elapsed / 60) * 100)}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 font-mono">{elapsed}s elapsed</p>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="card text-center">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-sm text-gray-400 mt-1">{label}</div>
    </div>
  )
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

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score))
  const color = pct >= 75 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-700 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-mono w-10 text-right">{Math.round(pct)}</span>
    </div>
  )
}

export default function Dashboard() {
  const [videos, setVideos] = useState([])
  const [stats, setStats] = useState(null)
  const [costs, setCosts] = useState(null)
  const [strategy, setStrategy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [filter, setFilter] = useState('')
  const [minScore, setMinScore] = useState('')
  const { toast, show: showToast, dismiss } = useToast()

  const showError = (msg) => showToast(msg, 'error', 8000)

  const fetchData = useCallback(async () => {
    try {
      const params = {}
      if (filter) params.platform = filter
      if (minScore) params.min_score = minScore
      const [videosData, statsData, costData, strategyData] = await Promise.all([
        getScoredVideos(params),
        getStats(),
        getCostSummary(),
        getStrategy(),
      ])
      setVideos(videosData)
      setStats(statsData)
      setCosts(costData)
      setStrategy(strategyData)
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }, [filter, minScore])

  useEffect(() => { fetchData() }, [fetchData])

  const handleScrape = async () => {
    setScraping(true)
    try {
      const result = await triggerScrape()
      const per = result?.result?.per_platform || {}
      const errors = result?.result?.errors || {}
      const parts = []
      for (const [platform, counts] of Object.entries(per)) {
        if (counts.scraped > 0) {
          parts.push(`${platform}: ${counts.scraped} → ${counts.saved} gems`)
        }
      }
      for (const [platform, err] of Object.entries(errors)) {
        parts.push(`${platform}: error — ${err.slice(0, 60)}`)
      }
      const totalSaved = result?.result?.total_saved || 0
      const msg = parts.length > 0 ? parts.join(' | ') : 'No videos found'
      showToast(msg, totalSaved > 0 ? 'success' : 'warning', 10000)
      await fetchData()
      try {
        const s = await refreshStrategy()
        setStrategy(s)
      } catch (_) {}
    } catch (err) {
      showError('Scrape failed: ' + (err?.response?.data?.detail || err.message))
    } finally {
      setScraping(false)
    }
  }

  return (
    <div className="space-y-6">
      <Toast toast={toast} onDismiss={dismiss} />
      <ScrapeModal scraping={scraping} />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button onClick={handleScrape} disabled={scraping} className="btn-primary">
          Scrape Now
        </button>
      </div>

      {stats && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Scraped Videos" value={stats.total_scraped_videos} color="text-brand-400" />
            <StatCard label="Scored Videos" value={stats.total_scored_videos} color="text-green-400" />
            <StatCard label="Generated" value={stats.total_generated_videos} color="text-yellow-400" />
            <StatCard label="Uploads" value={stats.total_uploads} color="text-purple-400" />
          </div>
          {costs && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <StatCard label="Total Cost" value={`$${costs.total_cost.toFixed(4)}`} color="text-amber-400" />
              <StatCard label="Avg Cost/Video" value={`$${costs.average_cost_per_video.toFixed(6)}`} color="text-emerald-400" />
              <StatCard label="Scrape Cost" value={`$${costs.scrape_cost.toFixed(4)}`} color="text-rose-400" />
              <StatCard label="Generate Cost" value={`$${costs.generate_cost.toFixed(4)}`} color="text-sky-400" />
            </div>
          )}
        </div>
      )}

      {strategy && strategy.videos_analyzed > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Content Strategy (auto-detected from top videos)</h2>
            <button onClick={async () => { const s = await refreshStrategy(); setStrategy(s) }} className="btn-secondary text-xs px-3 py-1">
              Re-analyze
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
              <div className="text-gray-400 text-xs mb-1">Hook Style</div>
              <div className="text-white font-semibold capitalize">{strategy.recommended_hook_style.replace(/_/g, ' ')}</div>
              <div className="text-gray-500 text-xs mt-1">Avg score: {strategy.hook_performance?.[strategy.recommended_hook_style] || '—'}</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
              <div className="text-gray-400 text-xs mb-1">Caption Style</div>
              <div className="text-white font-semibold capitalize">{strategy.recommended_caption_style.replace(/_/g, ' ')}</div>
              <div className="text-gray-500 text-xs mt-1">Avg score: {strategy.caption_performance?.[strategy.recommended_caption_style] || '—'}</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
              <div className="text-gray-400 text-xs mb-1">Duration / Resolution</div>
              <div className="text-white font-semibold">{strategy.recommended_duration}s</div>
              <div className="text-gray-400 text-xs">{strategy.recommended_resolution}</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
              <div className="text-gray-400 text-xs mb-1">Top Hashtag</div>
              <div className="text-brand-400 font-semibold">#{strategy.recommended_hashtags?.[0] || '—'}</div>
              <div className="text-gray-500 text-xs mt-1">Music: {strategy.recommend_music ? 'Yes' : 'No'}</div>
            </div>
          </div>
          {strategy.hook_distribution && Object.keys(strategy.hook_distribution).length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-gray-400 mb-2">Hook distribution in top videos</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(strategy.hook_distribution).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([style, count]) => (
                  <span key={style} className={`text-xs px-2 py-1 rounded-full ${style === strategy.recommended_hook_style ? 'bg-brand-900 text-brand-300' : 'bg-gray-800 text-gray-400'}`}>
                    {style.replace(/_/g, ' ')}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <h2 className="text-lg font-semibold">Scored Videos</h2>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input text-sm"
          >
            <option value="">All Platforms</option>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <input
            type="number"
            placeholder="Min score"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            className="input text-sm w-24"
          />
          <button onClick={fetchData} className="btn-secondary text-sm">Refresh</button>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">Loading...</div>
        ) : videos.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            No scored videos yet. Click "Scrape Now" to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-800">
                  <th className="pb-3 pr-4">Score</th>
                  <th className="pb-3 pr-4">Platform</th>
                  <th className="pb-3 pr-4">Caption</th>
                  <th className="pb-3 pr-4">Engagement</th>
                  <th className="pb-3 pr-4">Link</th>
                  <th className="pb-3 pr-4">Hashtags</th>
                  <th className="pb-3 pr-4">Music</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-3 pr-4 w-32">
                      <ScoreBar score={v.virality_score} />
                    </td>
                    <td className="py-3 pr-4">
                      <PlatformBadge platform={v.platform} />
                    </td>
                    <td className="py-3 pr-4 max-w-xs truncate text-gray-300">
                      {v.caption || '-'}
                    </td>
                      <td className="py-3 pr-4 text-gray-300">
                        <div>❤️ {v.likes?.toLocaleString()}</div>
                        <div>👁 {v.views?.toLocaleString()}</div>
                      </td>
                      <td className="py-3 pr-4">
                        {v.video_url ? (
                          <a href={v.video_url} target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:text-brand-300 underline text-xs" title={v.video_url}>
                            Open ↗
                          </a>
                        ) : '-'}
                      </td>
                      <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {(v.hashtags || []).slice(0, 3).map((h, i) => (
                          <span key={i} className="text-xs text-brand-300">#{h}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-gray-400 text-xs max-w-[120px] truncate">
                      {v.music || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
