import { useState, useEffect } from 'react'
import { getSchedule, updateSchedule } from '../api'

const INTERVAL_OPTIONS = [
  { value: 1, label: 'Every 1 hour' },
  { value: 12, label: 'Every 12 hours' },
  { value: 24, label: 'Every 24 hours (recommended)' },
  { value: 168, label: 'Every 7 days' },
  { value: 720, label: 'Every 30 days' },
]

export default function ScheduleSettings() {
  const [schedule, setSchedule] = useState({ interval_hours: 24, active: true })
  const [selectedInterval, setSelectedInterval] = useState(24)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSchedule()
      .then((data) => {
        setSchedule(data)
        setSelectedInterval(data.interval_hours)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const result = await updateSchedule(selectedInterval)
      setSchedule((prev) => ({ ...prev, interval_hours: selectedInterval }))
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to update schedule:', err)
    } finally {
      setSaving(false)
    }
  }

  const intervalLabel = (hours) => {
    const opt = INTERVAL_OPTIONS.find((o) => o.value === hours)
    return opt ? opt.label : `${hours} hours`
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Schedule Settings</h1>

      <div className="card max-w-2xl">
        <h2 className="text-lg font-semibold mb-2">Scan Frequency</h2>
        <p className="text-sm text-gray-400 mb-6">
          Configure how often the system scrapes platforms and scores videos.
          Current schedule: <span className="text-brand-300 font-medium">{intervalLabel(schedule.interval_hours)}</span>
          {!schedule.active && <span className="text-yellow-400 ml-2">(paused)</span>}
        </p>

        <div className="space-y-3 mb-6">
          {INTERVAL_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                selectedInterval === opt.value
                  ? 'border-brand-500 bg-brand-500/10'
                  : 'border-gray-700 hover:border-gray-600'
              }`}
            >
              <input
                type="radio"
                name="interval"
                value={opt.value}
                checked={selectedInterval === opt.value}
                onChange={() => setSelectedInterval(opt.value)}
                className="accent-brand-500"
              />
              <div>
                <div className="text-sm font-medium">{opt.label}</div>
                {opt.label.includes('recommended') && (
                  <div className="text-xs text-brand-400">Balanced between freshness and API usage</div>
                )}
              </div>
            </label>
          ))}
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleSave}
            disabled={saving || selectedInterval === schedule.interval_hours}
            className="btn-primary"
          >
            {saving ? 'Saving...' : 'Save Schedule'}
          </button>
          {saved && (
            <span className="text-green-400 text-sm">Schedule updated successfully</span>
          )}
        </div>
      </div>

      <div className="card max-w-2xl">
        <h2 className="text-lg font-semibold mb-2">What Happens at Each Interval</h2>
        <div className="space-y-2 text-sm text-gray-400">
          <p>⏱ <strong className="text-gray-300">Every run:</strong> The system scrapes trending videos from all 4 platforms, computes a virality score for each, and stores them in the database.</p>
          <p>🎬 <strong className="text-gray-300">Manual step:</strong> Video generation is triggered manually from the Generate tab. The scheduler only handles scraping.</p>
          <p>📤 <strong className="text-gray-300">Auto-upload:</strong> Can be enabled per-video in the Generate tab.</p>
        </div>
      </div>
    </div>
  )
}
