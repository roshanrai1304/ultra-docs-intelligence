import sys, traceback

print("Step 1: imports", flush=True)
from backend.ingestion.parser import parse_document
from backend.ingestion.chunker import chunk_text
from backend.retrieval.embedder import embed_texts, get_embedder
from backend.retrieval.vector_store import store_chunks
print("imports ok", flush=True)

print("Step 2: load embedder", flush=True)
ef = get_embedder()
print(f"embedder type: {type(ef)}", flush=True)

print("Step 3: parse", flush=True)
parsed = parse_document('/Users/abcom/Downloads/BOL53657_billoflading.pdf')
print(f"parsed: {len(parsed['raw_text'])} chars", flush=True)

print("Step 4: chunk", flush=True)
chunks = chunk_text(parsed['raw_text'], 'test-dbg')
print(f"chunks: {len(chunks)}", flush=True)

print("Step 5: embed", flush=True)
texts = [c['text'] for c in chunks]
print(f"embedding {len(texts)} texts", flush=True)
embeddings = embed_texts(texts)
print(f"embeddings shape: {len(embeddings)} x {len(embeddings[0])}", flush=True)

print("Step 6: store", flush=True)
store_chunks('test-dbg', chunks, embeddings)
print("DONE - all steps passed", flush=True)
