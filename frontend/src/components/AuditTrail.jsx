import { useState, useEffect } from 'react'
import './AuditTrail.css'

function AuditTrail({ apiBase }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAudit()
    const interval = setInterval(fetchAudit, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchAudit = async () => {
    try {
      const res = await fetch(`${apiBase}/audit?limit=20`)
      const data = await res.json()
      setEvents(data.events || [])
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  const getActionIcon = (action) => {
    if (action.includes('generate') && action.includes('completed')) return '✅'
    if (action.includes('generate') && action.includes('started')) return '⏳'
    if (action.includes('rejected')) return '🚫'
    if (action.includes('deploy')) return '🚀'
    if (action.includes('simulate')) return '▶️'
    if (action.includes('failed')) return '❌'
    if (action.includes('reset')) return '🔄'
    return '📝'
  }

  const formatTime = (ts) => {
    try {
      const d = new Date(ts)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return ts
    }
  }

  if (loading) return <div className="audit-panel"><p>Loading audit trail...</p></div>

  return (
    <div className="audit-panel">
      <h3>📋 Audit Trail</h3>
      {events.length === 0 ? (
        <p className="audit-empty">No events recorded yet.</p>
      ) : (
        <div className="audit-list">
          {events.map((evt, i) => (
            <div key={i} className="audit-event">
              <span className="audit-icon">{getActionIcon(evt.action)}</span>
              <span className="audit-action">{evt.action.replace(/_/g, ' ')}</span>
              {evt.details?.tenant_id && (
                <span className="audit-tenant">🏢 {evt.details.tenant_id}</span>
              )}
              {evt.details?.target_system && (
                <span className="audit-detail">{evt.details.target_system}</span>
              )}
              {evt.details?.service_name && (
                <span className="audit-detail">{evt.details.service_name}</span>
              )}
              {evt.details?.reason && (
                <span className="audit-detail">{evt.details.reason}</span>
              )}
              <span className="audit-time">{formatTime(evt.timestamp)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default AuditTrail
