import React from 'react'

const CONFIG = {
  high:    { color: '#16a34a', bg: '#dcfce7', label: 'HIGH' },
  medium:  { color: '#d97706', bg: '#fef3c7', label: 'MEDIUM' },
  low:     { color: '#dc2626', bg: '#fee2e2', label: 'LOW' },
  refused: { color: '#6b7280', bg: '#f3f4f6', label: 'REFUSED' },
}

export default function ConfidenceBadge({ score, label }) {
  const cfg = CONFIG[label] ?? CONFIG.refused
  const pct = Math.round((score ?? 0) * 100)
  const barWidth = `${pct}%`

  return (
    <div className="confidence-badge">
      <div className="confidence-row">
        <span
          className="confidence-pill"
          style={{ color: cfg.color, background: cfg.bg }}
        >
          {cfg.label}
        </span>
        <span className="confidence-score">{score?.toFixed(3) ?? '—'}</span>
      </div>
      <div className="confidence-track">
        <div
          className="confidence-bar"
          style={{ width: barWidth, background: cfg.color }}
        />
      </div>
    </div>
  )
}
