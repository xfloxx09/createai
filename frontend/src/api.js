import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export const getScoredVideos = (params = {}) =>
  api.get('/videos/scored', { params }).then((r) => r.data)

export const getTopVideos = (limit = 10) =>
  api.get('/videos/top', { params: { limit } }).then((r) => r.data)

export const triggerScrape = () =>
  api.post('/scrape/trigger').then((r) => r.data)

export const generateVideo = (platformFilter = null) =>
  api.post('/generate', { platform_filter: platformFilter }).then((r) => r.data)

export const getGenerationStatus = (taskId) =>
  api.get(`/generate/${taskId}/status`).then((r) => r.data)

export const getGenerationResult = (taskId) =>
  api.get(`/generate/${taskId}/result`).then((r) => r.data)

export const listGeneratedVideos = () =>
  api.get('/generated').then((r) => r.data)

export const uploadVideo = (generatedVideoId, platforms, caption = null) =>
  api.post('/upload', { generated_video_id: generatedVideoId, platforms, caption }).then((r) => r.data)

export const getUploadLog = (limit = 50) =>
  api.get('/upload/log', { params: { limit } }).then((r) => r.data)

export const getSchedule = () =>
  api.get('/schedule').then((r) => r.data)

export const updateSchedule = (intervalHours) =>
  api.put('/schedule', { interval_hours: intervalHours }).then((r) => r.data)

export const getStats = () =>
  api.get('/stats').then((r) => r.data)

export const getVideoDownloadUrl = (videoId) =>
  `/api/generated/${videoId}/download`

export const getVideoThumbnailUrl = (videoId) =>
  `/api/generated/${videoId}/thumbnail`

export const getAdminConfig = (key) =>
  api.get(`/admin/config/${key}`).then((r) => r.data)

export const updateAdminConfig = (key, value) =>
  api.put(`/admin/config/${key}`, value).then((r) => r.data)

export const getCostSummary = () =>
  api.get('/stats/costs').then((r) => r.data)

export const getCostEstimate = (platforms = 'instagram,tiktok,youtube,facebook', count = 10) =>
  api.get('/stats/costs/estimate', { params: { platforms, count } }).then((r) => r.data)

export default api
