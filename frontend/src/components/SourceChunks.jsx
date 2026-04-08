import React, { useState } from 'react'

export default function SourceChunks({ chunks }) {
  const [open, setOpen] = useState(false)

  if (!chunks || chunks.length === 0) return null

  return (
    <div className="source-chunks">
      <button className="toggle-btn" onClick={() => setOpen(o => !o)}>
        {open ? '▲' : '▼'} Source chunks ({chunks.length})
      </button>

      {open && (
        <div className="chunks-list">
          {chunks.map((c, i) => (
            <div key={c.chunk_id ?? i} className="chunk-card">
              <div className="chunk-meta">
                <span className="chunk-index">Chunk {i + 1}</span>
                <span className="chunk-sim">
                  similarity: <strong>{c.similarity?.toFixed(4)}</strong>
                </span>
              </div>
              <pre className="chunk-text">{c.text}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
