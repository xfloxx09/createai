import { useState, useEffect, useCallback } from 'react'
import { getAdminConfig, updateAdminConfig } from '../api'

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
                        type={subVal === '' ? 'text' : 'text'}
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

export default function Admin() {
  const [activeTab, setActiveTab] = useState('scrape')
  const [configs, setConfigs] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const tabs = [
    { key: 'scrape', label: 'Scrape' },
    { key: 'generate', label: 'Generate' },
    { key: 'upload', label: 'Upload' },
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
    fetchConfig()
  }, [fetchConfig])

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Admin Settings</h1>
      </div>

      <div className="flex gap-3 mb-6">
        {tabs.map((t) => (
          <AdminTab key={t.key} label={t.label} active={activeTab === t.key} onClick={() => setActiveTab(t.key)} />
        ))}
      </div>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <ConfigSection title={tabs.find((t) => t.key === activeTab)?.label} config={configs[activeTab]} onChange={handleChange} />
      </div>

      <div className="flex items-center gap-4">
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