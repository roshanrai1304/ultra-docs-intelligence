import React, { useRef, useState } from 'react'
import { uploadDoc } from '../api/client'

export default function UploadPanel({ onUploaded }) {
  const inputRef        = useRef(null)
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')  // idle | uploading | done | error
  const [info, setInfo]     = useState(null)
  const [error, setError]   = useState('')

  function handleFileChange(e) {
    const f = e.target.files[0]
    if (f) { setFile(f); setStatus('idle'); setInfo(null); setError('') }
  }

  async function handleUpload() {
    if (!file) return
    setStatus('uploading')
    setError('')
    try {
      const data = await uploadDoc(file)
      setInfo(data)
      setStatus('done')
      onUploaded(data)
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
      setStatus('error')
    }
  }

  return (
    <section className="panel">
      <h2 className="panel-title">
        <span className="step-num">1</span> Upload Document
      </h2>

      <div className="upload-row">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          className="btn btn-secondary"
          onClick={() => inputRef.current.click()}
        >
          Choose file
        </button>
        <span className="file-name">
          {file ? file.name : 'No file selected'}
        </span>
        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!file || status === 'uploading'}
        >
          {status === 'uploading' ? 'Uploading…' : 'Upload'}
        </button>
      </div>

      {status === 'uploading' && (
        <div className="alert alert-info">
          <strong>Processing…</strong> Parsing document, creating embeddings.
          On first run the embedding model downloads (~90 MB) — this may take up to 2 minutes.
        </div>
      )}

      {status === 'done' && info && (
        <div className="alert alert-success">
          <strong>✓ Ready</strong> — {info.filename} &nbsp;·&nbsp;
          {info.chunk_count} chunk{info.chunk_count !== 1 ? 's' : ''} &nbsp;·&nbsp;
          {info.page_count} page{info.page_count !== 1 ? 's' : ''} &nbsp;·&nbsp;
          <code className="doc-id">{info.doc_id}</code>
        </div>
      )}

      {status === 'error' && (
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <p className="hint">Supported formats: PDF, DOCX, TXT</p>
    </section>
  )
}
