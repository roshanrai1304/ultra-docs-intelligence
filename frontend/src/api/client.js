import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? ''

export async function uploadDoc(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await axios.post(`${BASE}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data   // { doc_id, filename, chunk_count, page_count, doc_type, status }
}

export async function askQuestion(docId, question) {
  const { data } = await axios.post(`${BASE}/ask`, { doc_id: docId, question })
  return data   // { answer, source_chunks, confidence_score, confidence_label, guardrail_triggered, guardrail_reason }
}

export async function extractFields(docId) {
  const { data } = await axios.post(`${BASE}/extract`, { doc_id: docId })
  return data   // { shipment_id, shipper, consignee, ... }
}
