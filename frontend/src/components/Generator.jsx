import { useState, useEffect, useCallback } from 'react'
import ReactPlayer from 'react-player'
import { generateVideo, getGenerationStatus, getGenerationResult, listGeneratedVideos, uploadVideo, getVideoDownloadUrl, getVideoThumbnailUrl } from '../api'

const PLATFORMS = [
  { id: 'instagram', label: 'Instagram Reels', color: 'pink' },
  { id: 'tiktok', label: 'TikTok', color: 'cyan' },
  { id: 'youtube', label: 'YouTube Shorts', color: 'red' },
  { id: 'facebook', label: 'Facebook Reels', color: 'blue' },
]

export default function Generator() {
  const [generatedVideos, setGeneratedVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [taskStatus, setTaskStatus] = useState(null)
  const [selectedPlatforms, setSelectedPlatforms] = useState(['instagram', 'tiktok'])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [autoUpload, setAutoUpload] = useState(false)

  const fetchGenerated = useCallback(async () => {
    try {
      const data = await listGeneratedVideos()
      setGeneratedVideos(data)
    } catch (err) {
      console.error('Failed to fetch generated videos:', err)
    }
  }, [])

  useEffect(() => { fetchGenerated() }, [fetchGenerated])

  useEffect(() => {
    if (!taskId || taskStatus === 'SUCCESS' || taskStatus === 'FAILURE') return
    const interval = setInterval(async () => {
      try {
        const status = await getGenerationStatus(taskId)
        setTaskStatus(status.status)
        if (status.ready) {
          clearInterval(interval)
          if (status.status === 'SUCCESS') {
            fetchGenerated()
          }
        }
      } catch (err) {
        clearInterval(interval)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [taskId, taskStatus, fetchGenerated])

  const handleGenerate = async () => {
    setGenerating(true)
    setTaskStatus('PENDING')
    setUploadResult(null)
    try {
      const result = await generateVideo()
      setTaskId(result.task_id)
      setTaskStatus('QUEUED')
    } catch (err) {
      console.error('Generation failed:', err)
      setTaskStatus('FAILURE')
    } finally {
      setGenerating(false)
    }
  }

  const handleRegenerate = () => {
    setSelectedVideo(null)
    setUploadResult(null)
    handleGenerate()
  }

  const togglePlatform = (id) => {
    setSelectedPlatforms((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  const handleUpload = async (video) => {
    if (selectedPlatforms.length === 0) return
    setUploading(true)
    setUploadResult(null)
    try {
      const result = await uploadVideo(video.id, selectedPlatforms)
      setUploadResult({ status: 'queued', task_id: result.task_id, platforms: selectedPlatforms })
    } catch (err) {
      setUploadResult({ status: 'failed', error: err.message })
    } finally {
      setUploading(false)
    }
  }

  useEffect(() => {
    if (autoUpload && selectedVideo && selectedPlatforms.length > 0) {
      handleUpload(selectedVideo)
    }
  }, [autoUpload, selectedVideo])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Video Generator</h1>
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn-primary"
          >
            {generating ? 'Generating...' : 'Generate New Video'}
          </button>
          {selectedVideo && (
            <button onClick={handleRegenerate} className="btn-secondary">
              Regenerate
            </button>
          )}
        </div>
      </div>

      {taskStatus && taskStatus !== 'SUCCESS' && taskStatus !== 'FAILURE' && (
        <div className="card border-brand-500/30">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-brand-500 border-t-transparent" />
            <span className="text-brand-300">
              Generation {taskStatus.toLowerCase()}...
            </span>
          </div>
        </div>
      )}

      {selectedVideo && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Generated Video</h2>
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="w-full lg:w-80 aspect-[9/16] bg-black rounded-lg overflow-hidden">
              <ReactPlayer
                url={getVideoDownloadUrl(selectedVideo.id)}
                controls
                width="100%"
                height="100%"
                light={getVideoThumbnailUrl(selectedVideo.id)}
              />
            </div>
            <div className="flex-1 space-y-4">
              <div>
                <h3 className="text-sm text-gray-400 mb-1">Hook Text</h3>
                <p className="text-lg font-medium">{selectedVideo.hook_text}</p>
              </div>
              <div>
                <h3 className="text-sm text-gray-400 mb-1">Caption</h3>
                <p className="text-sm text-gray-300">{selectedVideo.caption}</p>
              </div>
              <div>
                <h3 className="text-sm text-gray-400 mb-1">Duration</h3>
                <p className="text-sm">{selectedVideo.duration}s</p>
              </div>

              {selectedVideo.pattern_breakdown && (
                <div>
                  <h3 className="text-sm text-gray-400 mb-2">Pattern Breakdown</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-gray-800 rounded p-2">
                      <span className="text-gray-400">Avg Score: </span>
                      <span className="font-mono">{selectedVideo.pattern_breakdown.avg_virality_score}</span>
                    </div>
                    <div className="bg-gray-800 rounded p-2">
                      <span className="text-gray-400">Source Videos: </span>
                      <span>{selectedVideo.pattern_breakdown.source_count}</span>
                    </div>
                    <div className="bg-gray-800 rounded p-2">
                      <span className="text-gray-400">Style: </span>
                      <span>{selectedVideo.pattern_breakdown.caption_structure}</span>
                    </div>
                    <div className="bg-gray-800 rounded p-2">
                      <span className="text-gray-400">Overlay: </span>
                      <span>{selectedVideo.pattern_breakdown.text_overlay_position}</span>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <h3 className="text-sm text-gray-400 mb-2">Upload To</h3>
                <div className="flex flex-wrap gap-2 mb-3">
                  {PLATFORMS.map((p) => (
                    <label
                      key={p.id}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                        selectedPlatforms.includes(p.id)
                          ? 'border-brand-500 bg-brand-500/10'
                          : 'border-gray-700 hover:border-gray-600'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPlatforms.includes(p.id)}
                        onChange={() => togglePlatform(p.id)}
                        className="sr-only"
                      />
                      <span className="text-sm">{p.label}</span>
                    </label>
                  ))}
                </div>

                <div className="flex items-center gap-4">
                  <button
                    onClick={() => handleUpload(selectedVideo)}
                    disabled={uploading || selectedPlatforms.length === 0}
                    className="btn-success"
                  >
                    {uploading ? 'Uploading...' : 'Upload Now'}
                  </button>
                  <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoUpload}
                      onChange={(e) => setAutoUpload(e.target.checked)}
                      className="rounded"
                    />
                    Auto-upload
                  </label>
                </div>
              </div>

              {uploadResult && (
                <div className={`p-3 rounded-lg text-sm ${
                  uploadResult.status === 'queued' ? 'bg-green-900/30 text-green-300 border border-green-700' :
                  uploadResult.status === 'failed' ? 'bg-red-900/30 text-red-300 border border-red-700' :
                  'bg-gray-800 text-gray-300'
                }`}>
                  {uploadResult.status === 'queued'
                    ? `Upload queued for: ${uploadResult.platforms.join(', ')}`
                    : `Upload failed: ${uploadResult.error}`}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Previously Generated</h2>
        {generatedVideos.length === 0 && !taskStatus ? (
          <div className="text-center py-8 text-gray-400">
            No videos generated yet. Click "Generate New Video" to start.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {generatedVideos.map((v) => (
              <div
                key={v.id}
                onClick={() => { setSelectedVideo(v); setUploadResult(null) }}
                className={`card cursor-pointer hover:border-brand-500/50 transition-colors ${
                  selectedVideo?.id === v.id ? 'border-brand-500' : ''
                }`}
              >
                <div className="aspect-[9/16] bg-gray-800 rounded-lg mb-3 overflow-hidden">
                  <img
                    src={getVideoThumbnailUrl(v.id)}
                    alt={v.hook_text}
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                </div>
                <p className="text-sm font-medium truncate">{v.hook_text}</p>
                <p className="text-xs text-gray-400 mt-1">{v.duration}s</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
