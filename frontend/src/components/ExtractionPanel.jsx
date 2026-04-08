import React, { useState } from 'react'
import { extractFields } from '../api/client'

const FIELD_LABELS = {
  shipment_id:       'Shipment ID',
  shipper:           'Shipper',
  consignee:         'Consignee',
  pickup_datetime:   'Pickup Date/Time',
  delivery_datetime: 'Delivery Date/Time',
  equipment_type:    'Equipment Type',
  mode:              'Mode',
  rate:              'Rate',
  currency:          'Currency',
  weight:            'Weight',
  carrier_name:      'Carrier Name',
}

export default function ExtractionPanel({ docId }) {
  const [status, setStatus] = useState('idle')   // idle | loading | done | error
  const [data, setData]     = useState(null)
  const [error, setError]   = useState('')
  const [view, setView]     = useState('table')  // table | json

  const disabled = !docId

  async function handleExtract() {
    if (!docId) return
    setStatus('loading')
    setData(null)
    setError('')
    try {
      const result = await extractFields(docId)
      setData(result)
      setStatus('done')
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
      setStatus('error')
    }
  }

  const filledCount = data
    ? Object.values(data).filter(v => v !== null && v !== undefined).length
    : 0
  const totalCount = Object.keys(FIELD_LABELS).length

  return (
    <section className={`panel ${disabled ? 'panel-disabled' : ''}`}>
      <h2 className="panel-title">
        <span className="step-num">3</span> Structured Extraction
        {disabled && <span className="disabled-hint"> — upload a document first</span>}
      </h2>

      <div className="extract-header">
        <p className="hint">
          Extracts shipment fields as structured JSON. Missing fields are returned as null.
        </p>
        <button
          className="btn btn-primary"
          onClick={handleExtract}
          disabled={disabled || status === 'loading'}
        >
          {status === 'loading' ? 'Extracting…' : 'Extract Fields'}
        </button>
      </div>

      {status === 'error' && (
        <div className="alert alert-error"><strong>Error:</strong> {error}</div>
      )}

      {status === 'done' && data && (
        <div className="extraction-result">
          {/* Header bar */}
          <div className="extraction-bar">
            <span className="fill-count">
              {filledCount} / {totalCount} fields found
            </span>
            <div className="view-toggle">
              <button
                className={`toggle-view-btn ${view === 'table' ? 'active' : ''}`}
                onClick={() => setView('table')}
              >
                Table
              </button>
              <button
                className={`toggle-view-btn ${view === 'json' ? 'active' : ''}`}
                onClick={() => setView('json')}
              >
                JSON
              </button>
            </div>
          </div>

          {/* Table view */}
          {view === 'table' && (
            <table className="extraction-table">
              <tbody>
                {Object.entries(FIELD_LABELS).map(([key, label]) => {
                  const val = data[key]
                  const isEmpty = val === null || val === undefined
                  return (
                    <tr key={key} className={isEmpty ? 'row-null' : 'row-filled'}>
                      <td className="field-label">{label}</td>
                      <td className="field-value">
                        {isEmpty
                          ? <span className="null-badge">null</span>
                          : String(val)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          {/* JSON view */}
          {view === 'json' && (
            <pre className="json-block">
              {JSON.stringify(data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </section>
  )
}
