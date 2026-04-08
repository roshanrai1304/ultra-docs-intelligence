# Ultra Doc-Intelligence — Full Architecture & Implementation Guide

> POC AI system for logistics document Q&A inside a Transportation Management System (TMS)
> Built on **Groq Free Tier** (LLM) + **Sentence Transformers** (local embeddings) + **ChromaDB** (local vector store)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Groq Free Tier — Constraints & Design Decisions](#2-groq-free-tier--constraints--design-decisions)
3. [Tech Stack](#3-tech-stack)
4. [Project Structure](#4-project-structure)
5. [Architecture Diagram](#5-architecture-diagram)
6. [Component Deep Dives](#6-component-deep-dives)
   - 6.1 Document Ingestion & Parsing
   - 6.2 Chunking Strategy
   - 6.3 Embedding & Vector Store
   - 6.4 RAG Pipeline
   - 6.5 Guardrails & Confidence Scoring
   - 6.6 Structured Extraction
   - 6.7 API Layer
   - 6.8 Frontend UI
7. [API Contract](#7-api-contract)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Failure Cases & Mitigations](#9-failure-cases--mitigations)
10. [Improvement Ideas](#10-improvement-ideas)
11. [Environment & Dependencies](#11-environment--dependencies)

---

## 1. System Overview

Ultra Doc-Intelligence is a RAG (Retrieval-Augmented Generation) system that:

- Accepts logistics documents (PDF, DOCX, TXT) uploaded by a user
- Parses, chunks, and embeds the document content into a local vector store
- Answers natural language questions strictly from document context
- Returns an answer + source chunks + confidence score
- Applies guardrails to refuse or flag low-confidence answers
- Extracts a predefined set of structured shipment fields as JSON

The system is designed to run **entirely locally** except for the LLM inference call, which goes to **Groq's free API**.

---

## 2. Groq Free Tier — Constraints & Design Decisions

### Groq Free Tier Limits (as of 2026)

| Model                    | RPM | RPD    | TPM        |
|--------------------------|-----|--------|------------|
| llama-3.3-70b-versatile  | 30  | 14,400 | 6,000      |
| llama-3.1-8b-instant     | 30  | 14,400 | 20,000     |
| mixtral-8x7b-32768       | 30  | 14,400 | 5,000      |
| gemma2-9b-it             | 30  | 14,400 | 15,000     |

### Key Constraints

1. **No embeddings API on Groq** — Must use local embeddings
2. **Token-per-minute (TPM) limits** — Context sent to Groq must be controlled
3. **Rate limits** — No batch calls; sequential per request

### Design Decisions Made Because of Groq

| Constraint | Design Decision |
|---|---|
| No embeddings API | Use `sentence-transformers` locally (`all-MiniLM-L6-v2`) — free, fast, no API call |
| TPM limit (6K for 70b) | Cap retrieved context to top-3 chunks, max ~1500 tokens per chunk → ~4500 context tokens |
| RPM limit (30/min) | Single synchronous endpoint; no parallel Groq calls |
| Best free model | Use `llama-3.3-70b-versatile` for Q&A (most capable); `llama-3.1-8b-instant` for extraction (faster, cheaper on tokens) |
| Context window | Keep system prompt + context + question under 5800 tokens total |

---

## 3. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **LLM** | Groq API — `llama-3.3-70b-versatile` | Free tier, fast inference, strong reasoning |
| **Embeddings** | `sentence-transformers` — `all-MiniLM-L6-v2` | Fully local, no API cost, 384-dim vectors, good semantic quality |
| **Vector Store** | ChromaDB (local, persistent) | Zero infra, file-based persistence, cosine similarity built-in |
| **PDF Parsing** | PyMuPDF (`fitz`) | Best text extraction quality for logistics PDFs |
| **DOCX Parsing** | `python-docx` | Standard DOCX library |
| **Backend** | FastAPI + Uvicorn | Async, fast, auto OpenAPI docs |
| **Frontend** | Vanilla HTML + CSS + JS (single file) | Zero framework overhead, easy to deploy anywhere |
| **Storage** | Local filesystem (uploads/) + ChromaDB (chroma_db/) | No cloud dependencies |

---

## 4. Project Structure

```
ultra-docs-intelligence/
│
├── backend/
│   ├── main.py                  # FastAPI app, all 3 endpoints
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── parser.py            # PDF/DOCX/TXT parsing
│   │   └── chunker.py           # Intelligent chunking logic
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── embedder.py          # Sentence transformer wrapper
│   │   └── vector_store.py      # ChromaDB operations
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # RAG orchestration
│   │   ├── prompts.py           # All LLM prompt templates
│   │   └── confidence.py        # Confidence scoring logic
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── extractor.py         # Structured field extraction
│   ├── guardrails/
│   │   ├── __init__.py
│   │   └── guardrails.py        # Guardrail checks
│   └── config.py                # All config constants
│
├── frontend/                        # React app (Vite)
│   ├── src/
│   │   ├── main.jsx                 # React entry point
│   │   ├── App.jsx                  # Root component, tab routing
│   │   ├── api/
│   │   │   └── client.js            # Axios API calls (upload/ask/extract)
│   │   ├── components/
│   │   │   ├── UploadPanel.jsx      # File upload + status
│   │   │   ├── QuestionPanel.jsx    # Q&A input + answer display
│   │   │   ├── SourceChunks.jsx     # Retrieved chunks + similarity scores
│   │   │   ├── ConfidenceBadge.jsx  # Colour-coded confidence indicator
│   │   │   └── ExtractionPanel.jsx  # Structured JSON extraction view
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── uploads/                     # Uploaded documents (gitignored)
├── chroma_db/                   # ChromaDB persistent storage (gitignored)
│
├── requirements.in              # Direct (unpinned) backend dependencies
├── requirements.txt             # Pinned/locked deps (generated by uv pip compile)
├── .env.example
├── .env                         # GROQ_API_KEY (gitignored)
└── ARCHITECTURE.md              # This document
```

---

## 5. Architecture Diagram

```
USER BROWSER
    │
    │  HTTP (upload / ask / extract)
    ▼
┌─────────────────────────────────────────────────────┐
│                    FastAPI Backend                   │
│                                                     │
│  POST /upload          POST /ask       POST /extract│
│       │                    │                │       │
│       ▼                    ▼                ▼       │
│  ┌──────────┐      ┌──────────────┐  ┌──────────┐  │
│  │  Parser  │      │ RAG Pipeline │  │Extractor │  │
│  │(PDF/DOCX/│      │              │  │          │  │
│  │  TXT)    │      │ 1. Embed Q   │  │ Prompt → │  │
│  └────┬─────┘      │ 2. Retrieve  │  │ Groq LLM │  │
│       │            │ 3. Guardrail │  │ → JSON   │  │
│  ┌────▼─────┐      │ 4. Groq LLM  │  └──────────┘  │
│  │ Chunker  │      │ 5. Confidence│                 │
│  └────┬─────┘      └──────┬───────┘                 │
│       │                   │                         │
│  ┌────▼─────┐      ┌──────▼───────┐                 │
│  │ Embedder │      │  ChromaDB    │                 │
│  │(local ST)│◄─────│  Vector      │                 │
│  └────┬─────┘      │  Store       │                 │
│       │            └──────────────┘                 │
│  ┌────▼─────┐                                       │
│  │ChromaDB  │                                       │
│  │ (store)  │                                       │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
                            │
                   Groq API (external)
                   llama-3.3-70b-versatile
```

---

## 6. Component Deep Dives

---

### 6.1 Document Ingestion & Parsing

**File:** `backend/ingestion/parser.py`

Each uploaded file is saved to `uploads/` with a unique `doc_id` (UUID). Then parsed based on file type.

---

#### The Table Problem (Critical for Logistics Docs)

Logistics documents are **table-heavy**. The BOL sample has 5 distinct tables:

| Table | Content |
|---|---|
| Header table | Load ID, Ship Date, Delivery Date, PO Number, Freight Charges, COD |
| Shipper / Consignee | Two-column: shipper name+address vs consignee name+address |
| 3rd Party / Transportation | Two-column: billing party vs carrier |
| Commodity table | Units, Description, Weight, Type, Class |
| Notes / COD Value | Two-column: notes vs COD amount |

**What goes wrong with naive text extraction (PyMuPDF default):**

```
# Raw text extracted left-to-right across columns:
"Shipper    Consignee
AAA ,      xyz ,
Los Angeles International Airport (LAX), World Way,   7470 Cherry Avenue, Fontana, CA 92336, USA
Los Angeles, CA, USA"
```

A question like *"Who is the consignee?"* retrieves a chunk containing both shipper
and consignee text merged together. The LLM has to guess which name belongs to which role.

**The fix — convert tables to key-value text before chunking:**

```
# After table-aware parsing:
"Shipper: AAA, Los Angeles International Airport (LAX), World Way, Los Angeles, CA, USA
Consignee: xyz, 7470 Cherry Avenue, Fontana, CA 92336, USA"
```

Now "Who is the consignee?" retrieves a chunk with a clear, unambiguous answer.

---

#### Parsing Strategy: Dual-pass (Table-aware + Narrative)

```
PDF  → pdfplumber (primary for tables) + PyMuPDF (fallback for text)
DOCX → python-docx  (paragraphs + explicit table cell iteration)
TXT  → plain read   (UTF-8 decode, no tables)
```

**Why pdfplumber for tables?**
- Has built-in `page.extract_tables()` that returns a 2D list of cells
- Handles multi-column logistics layouts correctly
- PyMuPDF is kept as fallback for pages with no detectable tables

**PDF Parsing Algorithm (two-pass):**

```python
import pdfplumber
import fitz  # PyMuPDF fallback

def parse_pdf(filepath: str) -> str:
    blocks = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:

            # Pass 1: Extract tables as key-value text
            tables = page.extract_tables()
            table_bboxes = [t.bbox for t in page.find_tables()]

            for table in tables:
                kv_lines = table_to_kv(table)
                blocks.append("\n".join(kv_lines))

            # Pass 2: Extract non-table text (outside table bounding boxes)
            # Crop page to exclude table regions, extract remaining text
            non_table_text = extract_text_outside_tables(page, table_bboxes)
            if non_table_text.strip():
                blocks.append(non_table_text.strip())

    return "\n\n".join(blocks)


def table_to_kv(table: list[list]) -> list[str]:
    """
    Convert a 2D table array to key:value lines.

    Handles two layouts:
    1. Header row + data rows  →  "Header: Value"
    2. Two-column label/value  →  "Label: Value"
    """
    lines = []
    if not table or not table[0]:
        return lines

    # Detect if first row is a header row (non-empty, no numbers)
    first_row = [cell or "" for cell in table[0]]
    has_header = all(not cell.strip().lstrip("-").isnumeric() for cell in first_row if cell.strip())

    if has_header and len(table) > 1:
        headers = first_row
        for row in table[1:]:
            for i, cell in enumerate(row):
                if cell and cell.strip() and i < len(headers) and headers[i].strip():
                    lines.append(f"{headers[i].strip()}: {cell.strip()}")
    else:
        # Two-column key-value layout (e.g., Shipper | Consignee)
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            non_empty = [c for c in cells if c]
            if len(non_empty) == 2:
                lines.append(f"{non_empty[0]}: {non_empty[1]}")
            elif len(non_empty) == 1:
                lines.append(non_empty[0])
            elif len(non_empty) > 2:
                # Multi-column row: join with " | "
                lines.append(" | ".join(non_empty))
    return lines
```

**What the BOL produces after table-aware parsing:**

```
# Header table
Load ID: LD53657
Ship Date: 02-08-2026 09:00
Delivery Date: 02-08-2026 09:00
PO Number Pickup: 112233ABC
Freight Charges: Collect
COD: Prepaid

# Shipper/Consignee table
Shipper: AAA, Los Angeles International Airport (LAX), World Way, Los Angeles, CA, USA
Consignee: xyz, 7470 Cherry Avenue, Fontana, CA 92336, USA

# Commodity table
# Of Units | Description Of The Commodity | Weight | Type | Class
#10000 | Ceramic | 56000 lbs | N/A | N/A

# Notes/COD table
Notes: abc test notes
COD Value: $64000 USD
```

Every field is now a clean, retrievable `Label: Value` line.

**DOCX Parsing (explicit table cell iteration):**

```python
def parse_docx(filepath: str) -> str:
    doc = Document(filepath)
    blocks = []

    for element in doc.element.body:
        tag = element.tag.split('}')[-1]

        if tag == 'p':
            para = element.text.strip()
            if para:
                blocks.append(para)

        elif tag == 'tbl':
            # Iterate table rows and cells explicitly
            table = doc.tables[...]
            kv_lines = docx_table_to_kv(table)
            blocks.append("\n".join(kv_lines))

    return "\n\n".join(blocks)
```

**Output of parser — structured text block:**
```python
{
  "doc_id": "uuid-string",
  "filename": "BOL53657.pdf",
  "doc_type": "pdf",
  "raw_text": "Load ID: LD53657\nShip Date: 02-08-2026 09:00\n...\nShipper: AAA...\nConsignee: xyz...",
  "page_count": 2
}
```

---

### 6.2 Chunking Strategy

**File:** `backend/ingestion/chunker.py`

Logistics documents are structured (tables, fields, labels). A naive fixed-size chunker will cut across "Load ID | LD53657" pairs. The strategy used is **sliding window chunking with semantic boundary awareness**.

#### Parameters
```python
CHUNK_SIZE    = 400   # tokens (≈ 300 words)
CHUNK_OVERLAP = 80    # tokens overlap between consecutive chunks
MIN_CHUNK_LEN = 50    # discard chunks shorter than this (e.g., blank pages)
```

#### Algorithm

Because the parser already converts tables to `Label: Value` lines, the chunker
works on **clean, structured text** — not raw multi-column output.

```
1. Split text into lines
2. Detect section boundaries by:
   - Blank lines (empty line = new section)
   - Lines that are ALL CAPS with no colon (section headers like "BILL OF LADING")
   - Lines ending in ":" with no value (standalone labels)
3. Group lines into sections — never split a section across chunks
4. Accumulate sections into chunks until CHUNK_SIZE (400 tokens) is reached
5. At chunk boundary: finish current section fully, then start new chunk
6. Add CHUNK_OVERLAP (80 tokens) = repeat last N lines of previous chunk
7. Attach metadata per chunk
```

**Example — how the BOL gets chunked:**

```
CHUNK 0:
  "Load ID: LD53657
   Ship Date: 02-08-2026 09:00
   Delivery Date: 02-08-2026 09:00
   PO Number Pickup: 112233ABC
   Freight Charges: Collect
   COD: Prepaid"

CHUNK 1:
  "Freight Charges: Collect        ← overlap from chunk 0
   COD: Prepaid                    ← overlap from chunk 0
   Shipper: AAA, Los Angeles International Airport (LAX), World Way, Los Angeles, CA, USA
   Consignee: xyz, 7470 Cherry Avenue, Fontana, CA 92336, USA
   3rd Party Billing: -
   Transportation Company: -"

CHUNK 2:
  "Consignee: xyz, 7470 Cherry Avenue, Fontana, CA 92336, USA   ← overlap
   # Of Units | Description Of The Commodity | Weight | Type | Class
   #10000 | Ceramic | 56000 lbs | N/A | N/A
   Notes: abc test notes
   COD Value: $64000 USD"
```

Now:
- "Who is the consignee?" → hits CHUNK 1, finds `Consignee: xyz...` unambiguously
- "What is the weight?" → hits CHUNK 2, finds `56000 lbs` tied to `Ceramic`
- "What is the Load ID?" → hits CHUNK 0, finds `Load ID: LD53657`

**Chunk metadata:**
```python
{
  "doc_id": "...",
  "chunk_id": "doc_id_chunk_0",
  "text": "Load ID: LD53657\nShip Date: ...",
  "char_start": 0,
  "char_end": 412,
  "page_hint": 1
}
```

#### Why NOT split sections across chunks

If `Shipper:` label lands in chunk N and its address in chunk N+1, retrieval for
"Who is the shipper?" might fetch only the label or only the address — neither is
a complete answer. Section-complete chunking guarantees that each `Label: Value`
pair always travels together.

---

### 6.3 Embedding & Vector Store

**Files:** `backend/retrieval/embedder.py`, `backend/retrieval/vector_store.py`

#### Embedder

```python
Model: sentence-transformers/all-MiniLM-L6-v2
- Dimension: 384
- Max tokens: 256 (sufficient for our chunk size)
- Speed: ~2000 sentences/sec on CPU
- Fully local, no API call, no cost
```

The model is loaded **once at app startup** into memory and reused across requests.

#### ChromaDB

```python
- Persistent local store at: ./chroma_db/
- One collection per document: collection name = doc_id
- Distance metric: cosine similarity
- Each chunk stored with: embedding + text + metadata
```

**Why a collection per document (not global)?**
- Isolates documents from each other — questions answered only from the uploaded doc
- Makes deletion/re-upload clean
- Avoids cross-document retrieval confusion

**Retrieval:**
```python
top_k = 3   # retrieve top 3 most similar chunks
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=top_k,
    include=["documents", "metadatas", "distances"]
)
# distances are cosine distances → convert to similarity: 1 - distance
```

---

### 6.4 RAG Pipeline

**File:** `backend/rag/pipeline.py`

Full flow for `POST /ask`:

```
1. Embed the user question (local, sentence-transformers)
2. Query ChromaDB → top-3 chunks + cosine similarity scores
3. Run guardrail checks (see 6.5)
4. Build prompt with retrieved context
5. Call Groq API → llama-3.3-70b-versatile
6. Calculate confidence score (see 6.5)
7. Return structured response
```

#### Prompt Template (`backend/rag/prompts.py`)

```
SYSTEM:
You are a logistics document assistant for a Transportation Management System.
Answer questions ONLY using the provided document context.
If the answer is not in the context, respond exactly with: "NOT_FOUND_IN_DOCUMENT"
Do not make assumptions or use external knowledge.
Be concise and precise.

CONTEXT:
[chunk 1 text]
---
[chunk 2 text]
---
[chunk 3 text]

USER QUESTION:
{question}

ANSWER:
```

**Token budget (Groq 70b TPM = 6000/min):**
```
System prompt:    ~120 tokens
3 chunks × 400:  ~1200 tokens
Question:         ~30 tokens
Answer:           ~200 tokens
Total:            ~1550 tokens  ← well within 6000 TPM limit
```

---

### 6.5 Guardrails & Confidence Scoring

**Files:** `backend/guardrails/guardrails.py`, `backend/rag/confidence.py`

#### Guardrails (applied BEFORE calling Groq)

```python
SIMILARITY_THRESHOLD = 0.30   # minimum cosine similarity to attempt answer

def check_guardrails(top_similarities: list[float]) -> GuardrailResult:
    max_sim = max(top_similarities)

    if max_sim < SIMILARITY_THRESHOLD:
        return GuardrailResult(
            passed=False,
            reason="No sufficiently relevant content found in the document.",
            action="REFUSE"
        )
    return GuardrailResult(passed=True)
```

If guardrail fails → return immediately without calling Groq (saves API quota):
```json
{
  "answer": "I could not find relevant information in the document to answer this question.",
  "source_chunks": [],
  "confidence_score": 0.0,
  "guardrail_triggered": true,
  "guardrail_reason": "Retrieval similarity below threshold"
}
```

If LLM returns "NOT_FOUND_IN_DOCUMENT" → return "Not found in document" response.

#### Confidence Scoring (composite heuristic)

The confidence score (0.0 – 1.0) is computed from 3 signals:

```python
def compute_confidence(
    top_similarities: list[float],   # cosine similarities from ChromaDB
    llm_answer: str,                 # raw answer text from Groq
    retrieved_chunks: list[str],     # chunk texts used as context
) -> float:

    # Signal 1: Retrieval Score (weight: 50%)
    # Average of top-3 cosine similarities
    retrieval_score = mean(top_similarities)  # 0.0 – 1.0

    # Signal 2: Answer Coverage Score (weight: 30%)
    # What fraction of answer words appear in retrieved chunks?
    # Catches hallucination: if LLM introduces terms not in context, score drops
    answer_words = set(answer.lower().split())
    context_words = set(" ".join(chunks).lower().split())
    overlap = answer_words & context_words
    coverage_score = len(overlap) / max(len(answer_words), 1)

    # Signal 3: Answer Validity Score (weight: 20%)
    # Penalize vague or refusal responses
    if "not found" in answer.lower() or "not in document" in answer.lower():
        validity_score = 0.0
    elif len(answer.strip()) < 10:
        validity_score = 0.2   # too short = suspicious
    else:
        validity_score = 1.0

    # Composite
    confidence = (
        0.50 * retrieval_score +
        0.30 * coverage_score  +
        0.20 * validity_score
    )

    return round(min(max(confidence, 0.0), 1.0), 3)
```

#### Confidence Interpretation

| Score | Meaning | System Behavior |
|---|---|---|
| 0.0 – 0.29 | Very low | Guardrail blocks answer |
| 0.30 – 0.49 | Low | Answer returned with warning flag |
| 0.50 – 0.74 | Medium | Answer returned normally |
| 0.75 – 1.0 | High | Answer returned with high confidence |

---

### 6.6 Structured Extraction

**File:** `backend/extraction/extractor.py`

Uses Groq `llama-3.1-8b-instant` (faster, more token-efficient) with a strict JSON extraction prompt applied to the **full document text** (not chunks — we want all fields, not just top-k relevant ones).

#### Fields to Extract

```
shipment_id, shipper, consignee, pickup_datetime, delivery_datetime,
equipment_type, mode, rate, currency, weight, carrier_name
```

#### Extraction Prompt

```
SYSTEM:
You are a structured data extractor for logistics documents.
Extract the following fields from the document text below.
Return ONLY a valid JSON object. Use null for missing fields.
Do not invent or infer values not explicitly stated.

Fields: shipment_id, shipper, consignee, pickup_datetime,
delivery_datetime, equipment_type, mode, rate, currency, weight, carrier_name

Field definitions:
- shipment_id: Load ID or Reference ID
- shipper: name and address of the shipping party
- consignee: name and address of the receiving party
- pickup_datetime: ISO format if possible, e.g. "2026-02-08T09:00:00"
- delivery_datetime: ISO format
- equipment_type: truck type (e.g., Flatbed, Dry Van, Reefer)
- mode: FTL, LTL, etc.
- rate: numeric rate value only
- currency: currency code (USD, etc.)
- weight: total weight with unit
- carrier_name: name of the transportation/carrier company

DOCUMENT TEXT:
{full_document_text}

JSON:
```

#### Response Parsing

```python
# Parse LLM JSON response with fallback
try:
    data = json.loads(llm_response)
except json.JSONDecodeError:
    # Try to extract JSON block from response using regex
    match = re.search(r'\{.*\}', llm_response, re.DOTALL)
    data = json.loads(match.group()) if match else {}

# Fill missing keys with null
REQUIRED_FIELDS = [
    "shipment_id", "shipper", "consignee", "pickup_datetime",
    "delivery_datetime", "equipment_type", "mode", "rate",
    "currency", "weight", "carrier_name"
]
for field in REQUIRED_FIELDS:
    data.setdefault(field, None)
```

---

### 6.7 API Layer

**File:** `backend/main.py`

Built with FastAPI. Three endpoints:

#### POST /upload
```
Input:  multipart/form-data — file (PDF/DOCX/TXT)
Output: { doc_id, filename, chunk_count, status }

Steps:
1. Save file to uploads/{doc_id}/
2. Parse text (parser.py)
3. Chunk text (chunker.py)
4. Embed chunks (embedder.py)
5. Store in ChromaDB collection named doc_id
6. Return doc_id for use in subsequent requests
```

#### POST /ask
```
Input:  { doc_id: str, question: str }
Output: {
  answer: str,
  source_chunks: [ { text: str, similarity: float } ],
  confidence_score: float,
  confidence_label: str,    # "high" | "medium" | "low" | "refused"
  guardrail_triggered: bool,
  guardrail_reason: str | null
}

Steps:
1. Embed question
2. Retrieve top-3 chunks from ChromaDB[doc_id]
3. Guardrail check
4. Build prompt + call Groq
5. Compute confidence
6. Return structured response
```

#### POST /extract
```
Input:  { doc_id: str }
Output: {
  shipment_id: str | null,
  shipper: str | null,
  consignee: str | null,
  pickup_datetime: str | null,
  delivery_datetime: str | null,
  equipment_type: str | null,
  mode: str | null,
  rate: number | null,
  currency: str | null,
  weight: str | null,
  carrier_name: str | null
}

Steps:
1. Load full text from uploads/{doc_id}/
2. Build extraction prompt
3. Call Groq (llama-3.1-8b-instant)
4. Parse JSON response
5. Return with nulls for missing fields
```

---

### 6.8 Frontend UI

**Stack:** React 18 + Vite + plain CSS (no UI framework — usability over aesthetics)

#### Component Tree

```
App.jsx
├── UploadPanel.jsx          # Step 1 — always visible
│     uploads file → stores doc_id in App state
│
├── QuestionPanel.jsx        # Step 2 — enabled after upload
│   ├── ConfidenceBadge.jsx  # colour-coded score pill
│   └── SourceChunks.jsx     # collapsible retrieved chunks
│
└── ExtractionPanel.jsx      # Step 3 — enabled after upload
      renders structured JSON as a labelled field table
```

#### State managed in App.jsx

```js
const [docId, setDocId] = useState(null);      // set after successful upload
const [filename, setFilename] = useState('');
```

`docId` is passed as a prop to `QuestionPanel` and `ExtractionPanel`.
Both panels are disabled (greyed out) until a document is uploaded.

#### Layout

```
┌─────────────────────────────────────────┐
│  Ultra Doc-Intelligence                 │
│  Powered by Groq + ChromaDB             │
├─────────────────────────────────────────┤
│  [1] Upload Document                    │
│      [ Choose File ]  [ Upload ]        │
│      ✓ BOL53657.pdf loaded (8 chunks)   │
├─────────────────────────────────────────┤
│  [2] Ask a Question                     │
│      ┌─────────────────────────────┐    │
│      │ What is the carrier rate?   │    │
│      └─────────────────────────────┘    │
│      [ Ask ]                            │
│                                         │
│  Answer:                                │
│  "The carrier rate is $1,000 USD        │
│   (Flatbed, FTL)."                      │
│                                         │
│  Confidence:  ● HIGH  0.81              │
│                                         │
│  Source Chunks (3):          [collapse] │
│  ┌─────────────────────────────────┐    │
│  │ "Rate Breakdown                 │    │
│  │  Flatbed: $1000.00 USD          │    │
│  │  Total: $1000.00 USD"           │    │
│  │ similarity: 0.89                │    │
│  └─────────────────────────────────┘    │
├─────────────────────────────────────────┤
│  [3] Structured Extraction              │
│      [ Extract Fields ]                 │
│                                         │
│  shipment_id    LD53657                 │
│  shipper        AAA, LAX...             │
│  consignee      xyz, Fontana...         │
│  pickup         2026-02-08T09:00:00     │
│  delivery       2026-02-08T09:00:00     │
│  equipment      Flatbed                 │
│  mode           FTL                     │
│  rate           1000                    │
│  currency       USD                     │
│  weight         56000 lbs               │
│  carrier_name   —                       │
└─────────────────────────────────────────┘
```

#### ConfidenceBadge colour logic

```js
// ConfidenceBadge.jsx
const label = score >= 0.75 ? 'HIGH'
            : score >= 0.50 ? 'MEDIUM'
            : score >= 0.30 ? 'LOW'
            : 'REFUSED';

const colour = { HIGH: 'green', MEDIUM: 'orange', LOW: 'red', REFUSED: 'grey' };
```

#### API client (`src/api/client.js`)

```js
const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const uploadDoc   = (file)           => /* POST /upload  multipart */
export const askQuestion = (docId, question) => /* POST /ask     JSON body */
export const extractData = (docId)           => /* POST /extract JSON body */
```

`VITE_API_URL` is set in `frontend/.env` (local) or as an env var on the hosting platform.

#### package.json (key fields)

```json
{
  "name": "ultra-docs-intelligence-ui",
  "private": true,
  "scripts": {
    "dev":   "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0"
  }
}
```

---

## 7. API Contract

### POST /upload

**Request:**
```
Content-Type: multipart/form-data
Body: file=<binary>
```

**Response 200:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "BOL53657.pdf",
  "chunk_count": 8,
  "status": "ready"
}
```

**Response 400:**
```json
{ "error": "Unsupported file type. Use PDF, DOCX, or TXT." }
```

---

### POST /ask

**Request:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "What is the carrier rate?"
}
```

**Response 200 (answered):**
```json
{
  "answer": "The carrier rate is $1,000.00 USD (Flatbed).",
  "source_chunks": [
    {
      "text": "Rate Breakdown\nFlatbed:$ 1000.00 USD\nTotal: $1000.00 USD",
      "similarity": 0.89,
      "chunk_id": "...chunk_3"
    }
  ],
  "confidence_score": 0.81,
  "confidence_label": "high",
  "guardrail_triggered": false,
  "guardrail_reason": null
}
```

**Response 200 (guardrail blocked):**
```json
{
  "answer": "I could not find relevant information in the document to answer this question.",
  "source_chunks": [],
  "confidence_score": 0.0,
  "confidence_label": "refused",
  "guardrail_triggered": true,
  "guardrail_reason": "Retrieval similarity below threshold (max: 0.18)"
}
```

---

### POST /extract

**Request:**
```json
{ "doc_id": "550e8400-e29b-41d4-a716-446655440000" }
```

**Response 200:**
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

---

## 8. Data Flow Diagrams

### Upload Flow

```
User uploads file
      │
      ▼
FastAPI /upload
      │
      ├──► Save to uploads/{doc_id}/{filename}
      │
      ├──► Parser (PDF/DOCX/TXT)
      │         └──► raw_text (string)
      │
      ├──► Chunker
      │         └──► chunks[] (text + metadata)
      │
      ├──► Embedder (sentence-transformers, LOCAL)
      │         └──► embeddings[] (384-dim vectors)
      │
      └──► ChromaDB.add(collection=doc_id)
                └──► Persisted to ./chroma_db/

Response: { doc_id, chunk_count, status }
```

### Ask Flow

```
User asks question
      │
      ▼
FastAPI /ask
      │
      ├──► Embedder (question → 384-dim vector, LOCAL)
      │
      ├──► ChromaDB.query(collection=doc_id, top_k=3)
      │         └──► [(chunk_text, similarity_score), ...]
      │
      ├──► Guardrail Check
      │         ├── max_similarity < 0.30?
      │         │     └──► REFUSE (no Groq call)
      │         └── PASS → continue
      │
      ├──► Build prompt (system + context chunks + question)
      │
      ├──► Groq API (llama-3.3-70b-versatile)
      │         └──► answer_text
      │
      ├──► Check: answer == "NOT_FOUND_IN_DOCUMENT"?
      │         └──► Return "Not found in document"
      │
      ├──► Confidence Scoring
      │         ├── retrieval_score  (50%)
      │         ├── coverage_score   (30%)
      │         └── validity_score   (20%)
      │
      └──► Response: { answer, source_chunks, confidence_score, ... }
```

### Extract Flow

```
User clicks Extract
      │
      ▼
FastAPI /extract
      │
      ├──► Load full text from uploads/{doc_id}/
      │
      ├──► Build extraction prompt (all fields defined)
      │
      ├──► Groq API (llama-3.1-8b-instant — faster)
      │         └──► JSON string
      │
      ├──► Parse JSON → fill missing fields with null
      │
      └──► Response: structured shipment JSON
```

---

## 9. Failure Cases & Mitigations

| Failure | Cause | Mitigation |
|---|---|---|
| Answer from outside document | LLM hallucination | Coverage score penalizes words not in context; "NOT_FOUND_IN_DOCUMENT" signal |
| Wrong answer on split tables | Chunk boundary cuts field/value pair | Overlap chunks + section-aware chunking |
| Groq rate limit (429) | >30 RPM | Return HTTP 429 with `retry_after` header; UI shows "Rate limited, try in Xs" |
| Same doc uploaded twice | Duplicate ChromaDB collection | Overwrite collection if `doc_id` already exists (or use filename hash as doc_id) |
| PDF with no extractable text | Scanned/image PDF | Detect empty parse output → return error: "Document appears to be image-based; OCR not supported in this version" |
| DOCX with complex tables | python-docx misses table cells | Explicit cell iteration: `table.rows[i].cells[j].text` — never rely on `.text` on the whole table |
| Two-column table (Shipper/Consignee) | pdfplumber merges columns | `table_to_kv()` detects 2-column layout → `"Shipper: AAA..."` and `"Consignee: xyz..."` on separate lines |
| Multi-row merged cells in PDF | pdfplumber returns `None` for merged cells | `cell or ""` guard + carry-forward the last non-empty header value |
| LLM returns malformed JSON on extract | Model wraps JSON in markdown | Strip ```json ... ``` wrappers with regex before parsing |
| Very short document (<50 tokens) | Single chunk, low retrieval diversity | Return answer with low confidence warning |

---

## 10. Improvement Ideas

| Area | Idea |
|---|---|
| **Embeddings** | Swap `all-MiniLM-L6-v2` for `all-mpnet-base-v2` for better accuracy at cost of speed |
| **Chunking** | Use `langchain.text_splitter.RecursiveCharacterTextSplitter` with custom logistics separators |
| **Multi-doc Q&A** | Allow uploading multiple docs (BOL + RC together) and query across them |
| **OCR Support** | Add `pytesseract` fallback for image-based PDFs |
| **Re-ranking** | Add cross-encoder re-ranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) after retrieval for better chunk selection |
| **Streaming** | Use Groq's streaming API (`stream=True`) to stream answers to UI token-by-token |
| **Caching** | Cache embeddings of common logistics questions to reduce compute |
| **Eval Framework** | Add automated evaluation using a small golden Q&A set against the sample docs |
| **Auth** | Add simple API key auth for hosted version |
| **Hosting** | Deploy backend on Railway (free tier), frontend on Vercel/Netlify |

---

## 11. Environment & Dependencies

### Package Manager: uv (backend) + npm (frontend)

Backend uses **uv** with the `requirements.in` → `requirements.txt` pip-compile workflow.
Frontend uses standard **npm** managed by Vite.

**Install uv (once, globally):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### Backend Dependencies

#### requirements.in
Direct, unpinned dependencies — this is what you edit:
```
fastapi
uvicorn[standard]
python-multipart
groq
sentence-transformers
chromadb
pdfplumber
PyMuPDF
python-docx
python-dotenv
pydantic
numpy
```

#### requirements.txt
Fully pinned lockfile — **never edit manually**, always generated:
```bash
uv pip compile requirements.in -o requirements.txt
```

Commit both files. `requirements.in` expresses intent; `requirements.txt` ensures
reproducible installs across all environments.

**To install from the lockfile:**
```bash
uv pip sync requirements.txt
```

**To add a new package:**
```bash
# 1. Add to requirements.in
echo "httpx" >> requirements.in
# 2. Recompile the lockfile
uv pip compile requirements.in -o requirements.txt
# 3. Sync the environment
uv pip sync requirements.txt
```

---

### .env.example
```
GROQ_API_KEY=your_groq_api_key_here
```

---

### Running Locally

#### Backend
```bash
# 1. Clone repo
git clone <repo-url>
cd ultra-docs-intelligence

# 2. Create virtual environment
uv venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install pinned dependencies
uv pip sync requirements.txt

# 4. Set API key
cp .env.example .env
# Edit .env — add GROQ_API_KEY

# 5. Start backend
uvicorn backend.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
cp .env.example .env             # set VITE_API_URL=http://localhost:8000
npm run dev                      # starts at http://localhost:5173
```

#### frontend/.env.example
```
VITE_API_URL=http://localhost:8000
```

---

### Common uv Commands
```bash
uv venv                                        # create .venv
uv pip sync requirements.txt                   # install exact pinned versions
uv pip compile requirements.in -o requirements.txt  # regenerate lockfile
uv pip install <package>                       # ad-hoc install (then recompile)
```

---

*Generated for Ultra Doc-Intelligence POC — Ultraship TMS AI Engineer Skill Test*
