import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Generator from './components/Generator'
import ScheduleSettings from './components/ScheduleSettings'
import UploadLog from './components/UploadLog'

function NavBar() {
  const linkClass = ({ isActive }) =>
    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive ? 'bg-brand-600 text-white' : 'text-gray-300 hover:text-white hover:bg-gray-800'
    }`

  return (
    <nav className="bg-gray-900 border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-brand-400">CreateAI</span>
            <span className="text-xs text-gray-500 hidden sm:inline">Video Mass Production</span>
          </div>
          <div className="flex items-center gap-2">
            <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
            <NavLink to="/generate" className={linkClass}>Generate</NavLink>
            <NavLink to="/schedule" className={linkClass}>Schedule</NavLink>
            <NavLink to="/uploads" className={linkClass}>Uploads</NavLink>
          </div>
        </div>
      </div>
    </nav>
  )
}

function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-950">
      <NavBar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/generate" element={<Generator />} />
          <Route path="/schedule" element={<ScheduleSettings />} />
          <Route path="/uploads" element={<UploadLog />} />
        </Routes>
      </Layout>
    </Router>
  )
}
