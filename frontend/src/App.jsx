import React, { useState } from 'react'
import UploadPanel from './components/UploadPanel'
import QuestionPanel from './components/QuestionPanel'
import ExtractionPanel from './components/ExtractionPanel'

export default function App() {
  const [docId, setDocId]       = useState(null)
  const [filename, setFilename] = useState('')

  function handleUploaded(info) {
    setDocId(info.doc_id)
    setFilename(info.filename)
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand">
            <div className="logo-mark">U</div>
            <div>
              <div className="header-title">Ultra Doc-Intelligence</div>
              <div className="header-sub">Logistics document Q&A · Powered by Groq + ChromaDB</div>
            </div>
          </div>
          {docId && (
            <div className="active-doc">
              <span className="active-dot" />
              <span className="active-label">{filename}</span>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="main">
        <UploadPanel onUploaded={handleUploaded} />
        <QuestionPanel docId={docId} />
        <ExtractionPanel docId={docId} />
      </main>

      <footer className="app-footer">
        Ultra Doc-Intelligence POC · Ultraship TMS
      </footer>
    </div>
  )
}
