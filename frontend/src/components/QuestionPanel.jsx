import React, { useState } from 'react'
import { askQuestion } from '../api/client'
import ConfidenceBadge from './ConfidenceBadge'
import SourceChunks from './SourceChunks'

const SUGGESTED = [
  'Who is the consignee?',
  'What is the carrier rate?',
  'When is pickup scheduled?',
  'What is the Load ID?',
  'What commodity is being shipped?',
  'What is the total weight?',
]

export default function QuestionPanel({ docId }) {
  const [question, setQuestion] = useState('')
  const [status, setStatus]     = useState('idle')   // idle | loading | done | error
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState('')

  const disabled = !docId

  async function handleAsk() {
    const q = question.trim()
    if (!q || !docId) return
    setStatus('loading')
    setResult(null)
    setError('')
    try {
      const data = await askQuestion(docId, q)
      setResult(data)
      setStatus('done')
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message)
      setStatus('error')
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }
  }

  function useSuggestion(q) {
    setQuestion(q)
    setResult(null)
  }

  return (
    <section className={`panel ${disabled ? 'panel-disabled' : ''}`}>
      <h2 className="panel-title">
        <span className="step-num">2</span> Ask a Question
        {disabled && <span className="disabled-hint"> — upload a document first</span>}
      </h2>

      {/* Suggested questions */}
      {!disabled && (
        <div className="suggestions">
          {SUGGESTED.map(q => (
            <button
              key={q}
              className="suggestion-chip"
              onClick={() => useSuggestion(q)}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="ask-row">
        <textarea
          className="question-input"
          rows={2}
          placeholder="e.g. Who is the consignee?"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <button
          className="btn btn-primary ask-btn"
          onClick={handleAsk}
          disabled={disabled || !question.trim() || status === 'loading'}
        >
          {status === 'loading' ? 'Thinking…' : 'Ask'}
        </button>
      </div>

      {status === 'error' && (
        <div className="alert alert-error"><strong>Error:</strong> {error}</div>
      )}

      {status === 'done' && result && (
        <div className="answer-block">
          {/* Guardrail notice */}
          {result.guardrail_triggered && (
            <div className="alert alert-warning">
              <strong>Guardrail triggered:</strong> {result.guardrail_reason}
            </div>
          )}

          {/* Answer */}
          <div className="answer-box">
            <div className="answer-label">Answer</div>
            <p className="answer-text">{result.answer}</p>
          </div>

          {/* Confidence */}
          <div className="answer-meta">
            <span className="meta-label">Confidence</span>
            <ConfidenceBadge
              score={result.confidence_score}
              label={result.confidence_label}
            />
          </div>

          {/* Source chunks */}
          <SourceChunks chunks={result.source_chunks} />
        </div>
      )}
    </section>
  )
}
