import { useState, useEffect, useCallback } from 'react'
import { getAdminConfig, updateAdminConfig, getCostSummary, getCostEstimate } from '../api'

function ConfigSection({ title, config, onChange }) {
  if (!config) return null
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      {Object.entries(config).map(([key, val]) => {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
        if (typeof val === 'boolean') {
          return (
            <label key={key} className="flex items-center gap-3 text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={config[key]}
                onChange={(e) => onChange(key, e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
              />
              {label}
            </label>
          )
        }
        if (typeof val === 'object' && !Array.isArray(val)) {
          return (
            <div key={key} className="ml-4 border-l border-gray-700 pl-4 space-y-3">
              <h4 className="text-md font-medium text-gray-400">{label}</h4>
              {Object.entries(val).map(([subKey, subVal]) => {
                const subLabel = subKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                return (
                  <div key={subKey} className="flex flex-col gap-1">
                    <label className="text-sm text-gray-400">{subLabel}</label>
                    {typeof subVal === 'boolean' ? (
                      <label className="flex items-center gap-2 text-gray-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={config[key][subKey]}
                          onChange={(e) => onChange(key, { ...config[key], [subKey]: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-brand-500 focus:ring-brand-500"
                        />
                        Enabled
                      </label>
                    ) : (
                      <input
                        type="text"
                        value={config[key][subKey] || ''}
                        onChange={(e) => onChange(key, { ...config[key], [subKey]: e.target.value })}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-full max-w-md"
                      />
                    )}
                  </div>
                )
              })}
            </div>
          )
        }
        const dropdownOptions = {
          hook_style: ['question', 'statement', 'cliffhanger', 'curiosity gap', 'statistic', 'story hook'],
          caption_style: ['standard', 'storytelling', 'educational', 'controversial', 'call to action', 'humorous'],
          resolution: ['1080x1920', '1920x1080', '720x1280', '720x720', '480x854'],
          whisper_model: ['tiny', 'base', 'small', 'medium', 'large'],
          stock_video_source: ['pexels', 'none'],
        }
        const opts = dropdownOptions[key]
        if (opts) {
          return (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-sm text-gray-400">{label}</label>
              <select
                value={config[key] ?? opts[0]}
                onChange={(e) => onChange(key, e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-full max-w-md"
              >
                {opts.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          )
        }
        return (
          <div key={key} className="flex flex-col gap-1">
            <label className="text-sm text-gray-400">{label}</label>
            <input
              type={val === '' ? 'text' : 'number'}
              value={config[key] ?? ''}
              onChange={(e) => onChange(key, e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-full max-w-md"
            />
          </div>
        )
      })}
    </div>
  )
}

function AdminTab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
        active ? 'bg-brand-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
      }`}
    >
      {label}
    </button>
  )
}

function ProviderTable({ category }) {
  const [providers, setProviders] = useState(null)
  useEffect(() => {
    fetch('/api/stats/costs')
      .then((r) => r.json())
      .then((d) => setProviders(d.providers?.[category]))
      .catch(() => {})
  }, [category])
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b border-gray-800">
            <th className="pb-3 pr-4">Provider</th>
            <th className="pb-3 pr-4">Cost</th>
            <th className="pb-3 pr-4">Tier</th>
            <th className="pb-3 pr-4">Notes</th>
          </tr>
        </thead>
        <tbody>
          {providers ? (
            Object.entries(providers).map(([key, p]) => (
              <tr key={key} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-3 pr-4 text-gray-200">
                  {p.link ? <a href={p.link} target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline">{p.name}</a> : p.name}
                </td>
                <td className="py-3 pr-4 text-gray-300">{p.cost}</td>
                <td className="py-3 pr-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    p.tier === 'Free' ? 'bg-green-900 text-green-300' :
                    p.tier === 'Freemium' ? 'bg-yellow-900 text-yellow-300' :
                    'bg-rose-900 text-rose-300'
                  }`}>{p.tier}</span>
                </td>
                <td className="py-3 pr-4 text-gray-400 text-xs">{p.notes}</td>
              </tr>
            ))
          ) : (
            <tr><td colSpan={4} className="py-4 text-center text-gray-500">Loading providers...</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function CostCalculator() {
  const [count, setCount] = useState(10)
  const [platforms, setPlatforms] = useState(['instagram', 'tiktok', 'youtube', 'facebook'])
  const [estimate, setEstimate] = useState(null)
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    getCostEstimate(platforms.join(','), count).then(setEstimate).catch(() => {})
    getCostSummary().then(setSummary).catch(() => {})
  }, [count, platforms])

  const togglePlatform = (p) => {
    setPlatforms((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p])
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Cost Calculator</h3>
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <div className="flex flex-wrap gap-2">
            {['instagram', 'tiktok', 'youtube', 'facebook'].map((p) => (
              <button
                key={p}
                onClick={() => togglePlatform(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  platforms.includes(p)
                    ? 'bg-brand-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">Videos:</label>
            <input
              type="number"
              min={1}
              max={1000}
              value={count}
              onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-gray-200 text-sm w-20 text-center"
            />
          </div>
        </div>
      </div>

      {estimate && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-brand-400">${estimate.total_per_batch.toFixed(6)}</div>
            <div className="text-sm text-gray-400">Total per batch ({count} videos)</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-emerald-400">${estimate.total_per_video.toFixed(6)}</div>
            <div className="text-sm text-gray-400">Cost per video</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-amber-400">{platforms.length}</div>
            <div className="text-sm text-gray-400">Platforms selected</div>
          </div>
        </div>
      )}

      {estimate && (
        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <h4 className="text-sm font-medium text-gray-300 mb-3">Breakdown</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Scrape</span>
              <span className="text-gray-200">${estimate.scrape.total.toFixed(6)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Generate (stock + whisper + render)</span>
              <span className="text-gray-200">${estimate.generate.total.toFixed(6)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Upload</span>
              <span className="text-gray-200">${estimate.upload.total.toFixed(6)}</span>
            </div>
            <div className="border-t border-gray-700 pt-2 flex justify-between font-medium">
              <span className="text-gray-300">Total</span>
              <span className="text-brand-400">${estimate.total_per_batch.toFixed(6)}</span>
            </div>
          </div>
        </div>
      )}

      {summary && (
        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <h4 className="text-sm font-medium text-gray-300 mb-3">Actual Total (all time)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-gray-400">Total Cost</div>
              <div className="text-lg font-semibold text-white">${summary.total_cost.toFixed(6)}</div>
            </div>
            <div>
              <div className="text-gray-400">Videos Generated</div>
              <div className="text-lg font-semibold text-white">{summary.videos_generated}</div>
            </div>
            <div>
              <div className="text-gray-400">Avg Cost / Video</div>
              <div className="text-lg font-semibold text-emerald-400">${summary.average_cost_per_video.toFixed(6)}</div>
            </div>
            <div>
              <div className="text-gray-400">Scrape Cost</div>
              <div className="text-lg font-semibold text-rose-400">${summary.scrape_cost.toFixed(6)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Admin() {
  const [activeTab, setActiveTab] = useState('scrape')
  const [configs, setConfigs] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const tabs = [
    { key: 'scrape', label: 'Scrape' },
    { key: 'generate', label: 'Generate' },
    { key: 'upload', label: 'Upload' },
    { key: 'costs', label: 'Costs & Providers' },
  ]

  const fetchConfig = useCallback(async () => {
    try {
      const data = await getAdminConfig(activeTab)
      setConfigs((prev) => ({ ...prev, [activeTab]: data.value }))
    } catch (err) {
      console.error('Failed to load config:', err)
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'costs') fetchConfig()
  }, [activeTab, fetchConfig])

  const handleChange = (key, value) => {
    setConfigs((prev) => {
      const next = { ...prev }
      const keys = key.split('.')
      if (keys.length === 1) {
        next[activeTab] = { ...next[activeTab], [key]: value }
      } else {
        next[activeTab] = { ...next[activeTab], [keys[0]]: { ...next[activeTab][keys[0]], [keys[1]]: value } }
      }
      return next
    })
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateAdminConfig(activeTab, configs[activeTab])
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      console.error('Failed to save config:', err)
    } finally {
      setSaving(false)
    }
  }

  const renderTabContent = () => {
    if (activeTab === 'costs') {
      return (
        <div className="space-y-8">
          <div>
            <h3 className="text-lg font-semibold text-white mb-3">Provider Suggestions</h3>
            <p className="text-sm text-gray-400 mb-4">Recommended services for each stage of the pipeline:</p>
            <div>
              <h4 className="text-sm font-medium text-gray-300 mb-2">Scraping</h4>
              <ProviderTable category="scrape" />
            </div>
            <div className="mt-6">
              <h4 className="text-sm font-medium text-gray-300 mb-2">Generation</h4>
              <ProviderTable category="generate" />
            </div>
            <div className="mt-6">
              <h4 className="text-sm font-medium text-gray-300 mb-2">Upload</h4>
              <ProviderTable category="upload" />
            </div>
          </div>
          <CostCalculator />
        </div>
      )
    }
    return (
      <div>
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <ConfigSection title={tabs.find((t) => t.key === activeTab)?.label} config={configs[activeTab]} onChange={handleChange} />
        </div>
        <div className="flex items-center gap-4 mt-6">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 rounded-lg text-white font-medium transition-colors"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {saved && <span className="text-green-400 text-sm font-medium">Saved successfully</span>}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Admin Settings</h1>
      </div>

      <div className="flex gap-3 mb-6 flex-wrap">
        {tabs.map((t) => (
          <AdminTab key={t.key} label={t.label} active={activeTab === t.key} onClick={() => setActiveTab(t.key)} />
        ))}
      </div>

      {renderTabContent()}
    </div>
  )
}
