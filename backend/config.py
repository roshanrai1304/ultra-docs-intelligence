import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"

UPLOAD_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# ── Groq ───────────────────────────────────────────────────────────────────────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
GROQ_QA_MODEL       = "llama-3.3-70b-versatile"   # best reasoning for Q&A
GROQ_EXTRACT_MODEL  = "llama-3.1-8b-instant"       # faster / cheaper for extraction
GROQ_MAX_TOKENS     = 512

# ── Embeddings ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # local, 384-dim, no API cost

# ── Chunking ───────────────────────────────────────────────────────────────────
# 150 tokens × 4 chars ≈ 600 chars per chunk.
# Smaller chunks keep each section focused (e.g. "Ship Date" section stays
# separate from "Shipper/Consignee" section), which gives sharper embeddings
# and better per-question retrieval scores.
CHUNK_SIZE    = 50    # approximate token target per chunk (50 × 4 ≈ 200 chars)
CHUNK_OVERLAP = 10    # tokens repeated at chunk boundaries
MIN_CHUNK_LEN = 20    # discard chunks shorter than this (chars)

# ── Retrieval ──────────────────────────────────────────────────────────────────
TOP_K                = 3     # number of chunks to retrieve
# 0.20 is intentionally lenient: logistics docs are dense with numbers and
# abbreviations that reduce raw cosine similarity. We rely on the LLM +
# confidence scorer to filter bad answers rather than blocking at retrieval.
SIMILARITY_THRESHOLD = 0.15  # minimum cosine similarity to attempt an answer

# ── Confidence weights ─────────────────────────────────────────────────────────
W_RETRIEVAL = 0.50
W_COVERAGE  = 0.30
W_VALIDITY  = 0.20

# ── Supported file types ───────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
