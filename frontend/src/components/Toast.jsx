import { useState, useEffect, useCallback } from 'react'

export function useToast() {
  const [toast, setToast] = useState(null)

  const show = useCallback((message, type = 'info', duration = 5000) => {
    setToast({ id: Date.now(), message, type, duration })
  }, [])

  const dismiss = useCallback(() => setToast(null), [])

  return { toast, show, dismiss }
}

const COLORS = {
  success: 'bg-green-900 border-green-600 text-green-200',
  error: 'bg-red-900 border-red-600 text-red-200',
  info: 'bg-blue-900 border-blue-600 text-blue-200',
  warning: 'bg-yellow-900 border-yellow-600 text-yellow-200',
}

export default function Toast({ toast, onDismiss }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!toast) { setVisible(false); return }
    setVisible(true)
    const timer = setTimeout(() => {
      setVisible(false)
      setTimeout(onDismiss, 300)
    }, toast.duration || 5000)
    return () => clearTimeout(timer)
  }, [toast, onDismiss])

  if (!toast) return null

  return (
    <div
      className={`fixed top-4 right-4 z-50 max-w-md transition-all duration-300 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'
      }`}
    >
      <div className={`px-4 py-3 rounded-lg border shadow-lg ${COLORS[toast.type] || COLORS.info}`}>
        <div className="flex items-start gap-3">
          <span className="text-sm flex-1">{toast.message}</span>
          <button onClick={() => { setVisible(false); setTimeout(onDismiss, 300) }} className="text-current opacity-60 hover:opacity-100 text-lg leading-none">&times;</button>
        </div>
      </div>
    </div>
  )
}
