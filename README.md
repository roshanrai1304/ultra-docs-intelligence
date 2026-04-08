# Ultra Doc-Intelligence

A RAG-based AI assistant for logistics documents. Upload a Bill of Lading, Rate Confirmation, Invoice, or any shipment document — then ask natural language questions, get grounded answers with confidence scores, or extract structured shipment data as JSON.

Built as a POC for a Transportation Management System (TMS) AI layer.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM (Q&A) | Groq — `llama-3.3-70b-versatile` |
| LLM (Extraction) | Groq — `llama-3.1-8b-instant` |
| Embeddings | ChromaDB built-in ONNX (`all-MiniLM-L6-v2`) |
| Vector Store | ChromaDB (local persistent) |
| PDF Parsing | pdfplumber (tables) + PyMuPDF (fallback) |
| Backend | FastAPI + Uvicorn |
| Frontend | React 18 + Vite |
| Package Manager | uv (backend) + npm (frontend) |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A free [Groq API key](https://console.groq.com)

### 1. Clone and configure

```bash
git clone <repo-url>
cd ultra-docs-intelligence
```

### 2. Set environment variables

```bash
cp .env.example .env
```

Open `.env` and set your Groq API key:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

Get a free key at [console.groq.com](https://console.groq.com) → **API Keys** → **Create API Key**.

> The key must start with `gsk_`. The app will fail to start without it.

### 3. Backend setup

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip sync requirements.txt
```

### 4. Frontend setup

```bash
cd frontend
npm install
```

### 5. Run

**Terminal 1 — Backend:**
```bash
cd ultra-docs-intelligence
./start_backend.sh
```

Wait for: `Application startup complete.`

> On first run, ChromaDB downloads the ONNX embedding model (~79 MB). This happens once and is cached at `~/.cache/chroma/`.

**Terminal 2 — Frontend:**
```bash
cd ultra-docs-intelligence/frontend
npm run dev
```

Open **http://localhost:5173**

### 6. Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

---

## API Reference

### `POST /upload`
Upload a logistics document (PDF, DOCX, TXT).

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/BOL53657.pdf"
```

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "BOL53657.pdf",
  "chunk_count": 8,
  "page_count": 2,
  "doc_type": "pdf",
  "status": "ready"
}
```

---

### `POST /ask`
Ask a natural language question about an uploaded document.

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "<doc_id>", "question": "What is the carrier rate?"}'
```

```json
{
  "answer": "The carrier rate is $1,000.00 USD (Flatbed).",
  "source_chunks": [
    {
      "chunk_id": "..._chunk_3",
      "text": "Rate Breakdown: Flatbed:$ 1000.00 USD\nTotal: $1000.00 USD",
      "similarity": 0.89
    }
  ],
  "confidence_score": 0.81,
  "confidence_label": "high",
  "guardrail_triggered": false,
  "guardrail_reason": null
}
```

---

### `POST /extract`
Extract structured shipment fields as JSON.

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "<doc_id>"}'
```

```json
{
  "shipment_id": "LD53657",
  "shipper": "AAA, Los Angeles International Airport (LAX), World Way, Los Angeles, CA, USA",
  "consignee": "xyz, 7470 Cherry Avenue, Fontana, CA 92336, USA",
  "pickup_datetime": "2026-02-08T09:00:00",
  "delivery_datetime": "2026-02-08T09:00:00",
  "equipment_type": "Flatbed",
  "mode": "FTL",
  "rate": 1000.00,
  "currency": "USD",
  "weight": "56000 lbs",
  "carrier_name": null
}
```

Interactive API docs: **http://localhost:8000/docs**

---

## Architecture

```
Browser (React + Vite)
        │
        │ POST /upload | /ask | /extract
        ▼
  FastAPI Backend
        │
   ┌────┴────────────────────────────────┐
   │                                     │
   ▼                                     ▼
/upload pipeline                   /ask pipeline
   │                                     │
   ├─ Parser (pdfplumber + PyMuPDF)      ├─ ChromaDB.query(query_text)
   ├─ Chunker (section-aware)            │    └─ ONNX embeds query internally
   └─ ChromaDB.add(texts)               ├─ Guardrail check
        └─ ONNX embeds internally        ├─ Groq LLM (llama-3.3-70b)
                                         └─ Confidence scorer
                                                              │
                                                   /extract pipeline
                                                        │
                                                        ├─ Full doc text
                                                        └─ Groq LLM (llama-3.1-8b)
                                                             JSON extraction
```

### Key design decision: Groq free tier

Groq's free tier has no embedding API and a 6,000 TPM limit on the 70b model. The system is designed around these constraints:

- **Embeddings**: ChromaDB's ONNX function runs locally — zero API cost, ~80 MB RAM
- **Token budget**: top-3 chunks × ~400 chars ≈ 1,500 context tokens per Q&A call — well within 6K TPM
- **Two models**: `llama-3.3-70b-versatile` for Q&A (quality), `llama-3.1-8b-instant` for extraction (speed/cost)

---

## Chunking Strategy

### The table problem

Logistics documents are table-heavy. A naive left-to-right text extraction of a two-column table like:

```
| Shipper        | Consignee      |
| AAA, LAX...    | xyz, Fontana.. |
```

produces garbled text: `"Shipper Consignee AAA xyz Los Angeles Fontana..."` — destroying the field→value relationship.

### Solution: dual-pass table-aware parsing

1. **pdfplumber** detects tables and extracts them as a 2D cell grid
2. `table_to_kv()` converts each table to clean `Label: Value` lines:
   ```
   Shipper: AAA, Los Angeles International Airport (LAX)...
   Consignee: xyz, 7470 Cherry Avenue, Fontana, CA...
   ```
3. **PyMuPDF** extracts non-table text from the remaining page area
4. DOCX files use explicit `table.rows[i].cells[j].text` iteration

Two-column tables (vertical key-value layout like BOL header) are distinguished from header+data tables (like commodity table) using a `_looks_like_value()` heuristic on the second cell of row 1.

### Chunking algorithm

After parsing, text is split into **sections** (delimited by blank lines, ALL-CAPS headers, and `---` page dividers), then sections are packed into chunks:

| Parameter | Value | Rationale |
|---|---|---|
| `CHUNK_SIZE` | 50 tokens (~200 chars) | Small enough to isolate individual sections (Ship Date, Shipper/Consignee, Commodity) into separate chunks |
| `CHUNK_OVERLAP` | 10 tokens (~40 chars) | Preserves continuity across boundaries |
| `MIN_CHUNK_LEN` | 20 chars | Drops blank-page artefacts |

**Critical rule**: sections are never split mid-way. A chunk always contains complete `Label: Value` pairs — never a label without its value.

A single oversized section is hard-split at character boundaries with an overlap guard to prevent infinite loops (`if new_start <= start: break`).

---

## Retrieval Method

**Model**: `all-MiniLM-L6-v2` via ChromaDB's ONNX embedding function
**Dimensions**: 384
**Distance metric**: cosine
**Top-k**: 3 chunks retrieved per query

The query text is passed directly to ChromaDB which embeds it internally alongside the stored chunk embeddings. This avoids PyTorch/sentence-transformers (which caused macOS MPS memory kills) and uses onnxruntime directly — stable at ~80 MB RAM.

**Similarity threshold**: `0.15`

Set intentionally lower than typical (0.3+) because logistics documents contain dense abbreviations, IDs, and numeric codes that reduce raw cosine similarity scores. Measured scores for the BOL document:

| Question | Similarity | Decision |
|---|---|---|
| "What is the ship date?" | 0.48 | PASS |
| "What is the delivery date?" | 0.41 | PASS |
| "Who is the consignee?" | 0.33 | PASS |
| "What is the Load ID?" | 0.30 | PASS |
| "What is the weather in Paris?" | 0.07 | BLOCK |

---

## Guardrails Approach

Two layers of guardrails prevent hallucination:

### Layer 1 — Retrieval similarity gate (pre-LLM)

```python
SIMILARITY_THRESHOLD = 0.15

if max(similarities) < SIMILARITY_THRESHOLD:
    return REFUSED  # no Groq API call made
```

If no retrieved chunk is similar enough to the question, the system refuses to answer **without calling the LLM**. This saves Groq quota and gives an honest response rather than a hallucinated one.

Response when triggered:
```
"I could not find relevant information in the document to answer this question."
```

### Layer 2 — NOT_FOUND signal (post-LLM)

The system prompt instructs the LLM:

> "If the answer is not present in the CONTEXT, respond with exactly: `NOT_FOUND_IN_DOCUMENT`"

If the LLM returns this signal, the system maps it to:
```
"Not found in document."
```

This catches cases where retrieval passes the threshold (document is related) but the specific answer isn't present in the retrieved chunks.

---

## Confidence Scoring

Each answer returns a composite score from 0.0 to 1.0 built from three signals:

### Signal 1 — Retrieval score (50% weight)
Average cosine similarity of the top-3 retrieved chunks. High similarity means the document genuinely contains content related to the question.

### Signal 2 — Coverage score (30% weight)
Fraction of answer words that appear in the retrieved context (excluding stop words):

```python
answer_words  = tokenise(answer) - STOPWORDS
context_words = tokenise(all_chunks) - STOPWORDS
coverage = len(answer_words ∩ context_words) / len(answer_words)
```

If the LLM introduces terms not present in the source chunks, coverage drops — a signal of potential hallucination.

### Signal 3 — Validity score (20% weight)
Penalises suspicious responses:
- Answer shorter than 10 chars → 0.2
- Contains "not found" / "not in document" phrases → 0.1
- Normal answer → 1.0

### Composite formula

```
score = 0.50 × retrieval + 0.30 × coverage + 0.20 × validity
```

### Labels

| Score | Label | Behaviour |
|---|---|---|
| ≥ 0.75 | `high` | Green badge |
| ≥ 0.50 | `medium` | Orange badge |
| ≥ 0.30 | `low` | Red badge |
| < 0.30 | `refused` | Grey badge |

---

## Failure Cases

| Failure | Cause | Current Mitigation |
|---|---|---|
| Scanned / image PDF | No extractable text | Returns HTTP 422 with clear message |
| Similarity below threshold for valid question | Dense abbreviations / short doc → diluted chunk embeddings | Threshold lowered to 0.15; small chunk size (200 chars) keeps embeddings focused |
| Chunker infinite loop on oversized section | `end - overlap` not advancing start | `if new_start <= start: break` guard |
| Stale uvicorn process blocking port 8000 | Previous process not killed before restart | `start_backend.sh` kills stale process before binding |
| Groq 429 rate limit | >30 RPM on free tier | Returns HTTP 503; UI shows error message |
| LLM wraps JSON in markdown on `/extract` | Model adds ` ```json ``` ` fences | Regex strips code fences before `json.loads()` |
| Two-column table misidentified as header+data | All cells are text in first row | `_looks_like_value()` heuristic checks col-2 of row 1 for digits / long strings |
| Re-upload same document | Duplicate ChromaDB collection | Collection is deleted and recreated on each upload |
| Very short document → 1 chunk | Section accumulation fills target before splitting | Chunk size of 50 tokens (200 chars) forces splits even on small documents |

---

## Improvement Ideas

| Area | Idea |
|---|---|
| **OCR** | Add `pytesseract` fallback for image-based PDFs — currently rejected |
| **Re-ranking** | Add a cross-encoder re-ranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) after initial retrieval for better chunk selection |
| **Streaming** | Use Groq's `stream=True` to stream answer tokens to the UI as they arrive |
| **Multi-document** | Allow uploading BOL + Rate Confirmation together; query across both with source attribution |
| **Confidence calibration** | Build a small golden Q&A set from sample docs; tune weights empirically rather than by heuristic |
| **Embeddings upgrade** | Swap `all-MiniLM-L6-v2` for `all-mpnet-base-v2` for better semantic quality at moderate cost |
| **Caching** | Cache embeddings for repeated questions on the same document |
| **Auth** | Add API key middleware for the hosted version |
| **Hosting** | Backend → Railway free tier; Frontend → Vercel/Netlify |
| **Eval framework** | Automated evaluation pipeline: upload sample docs, run known Q&A pairs, assert answers and confidence labels |

---

## Project Structure

```
ultra-docs-intelligence/
│
├── backend/
│   ├── main.py                   FastAPI app — /upload, /ask, /extract, /health
│   ├── config.py                 All constants (chunk size, threshold, models)
│   ├── ingestion/
│   │   ├── parser.py             PDF (pdfplumber+PyMuPDF), DOCX, TXT parsing
│   │   └── chunker.py            Section-aware sliding-window chunker
│   ├── retrieval/
│   │   ├── embedder.py           Thin wrapper (ChromaDB handles embedding internally)
│   │   └── vector_store.py       ChromaDB — one collection per document
│   ├── rag/
│   │   ├── pipeline.py           Full RAG orchestration for /ask
│   │   ├── prompts.py            LLM prompt templates
│   │   └── confidence.py         3-signal composite confidence scorer
│   ├── extraction/
│   │   └── extractor.py          Structured JSON field extraction via Groq
│   └── guardrails/
│       └── guardrails.py         Similarity threshold gate
│
├── frontend/
│   └── src/
│       ├── App.jsx               Root — holds doc_id state
│       ├── api/client.js         Axios wrappers for all 3 endpoints
│       └── components/
│           ├── UploadPanel.jsx
│           ├── QuestionPanel.jsx
│           ├── ConfidenceBadge.jsx
│           ├── SourceChunks.jsx
│           └── ExtractionPanel.jsx
│
├── requirements.in               Direct (unpinned) backend dependencies
├── requirements.txt              Pinned lockfile — generated by uv pip compile
├── start_backend.sh              Kills stale process + starts uvicorn
└── .env.example                  GROQ_API_KEY template
```

---

## Adding Dependencies

```bash
# Backend
echo "new-package" >> requirements.in
uv pip compile requirements.in -o requirements.txt
uv pip sync requirements.txt

# Frontend
cd frontend
npm install new-package
```

---

*Ultra Doc-Intelligence — AI Engineer Skill Test POC · Ultraship TMS*
