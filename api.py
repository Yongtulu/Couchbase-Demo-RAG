# api.py — FastAPI backend
#
# Start:  uvicorn api:app --host 127.0.0.1 --port 8000 --reload

import time
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator

from config import (
    COUCHBASE_HOST, COUCHBASE_USER, COUCHBASE_PASSWORD,
    COUCHBASE_BUCKET, COUCHBASE_SCOPE, COUCHBASE_COLLECTION,
    FTS_INDEX_NAME, OLLAMA_LLM_MODEL,
)
from search import retrieve, n1ql_verify
from llm import ask

app = FastAPI(title="Couchbase RAG Demo", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_cluster():
    auth = PasswordAuthenticator(COUCHBASE_USER, COUCHBASE_PASSWORD)
    c = Cluster(f"couchbase://{COUCHBASE_HOST}", ClusterOptions(auth))
    c.wait_until_ready(timedelta(seconds=10))
    return c


# ── models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class ChunkInfo(BaseModel):
    id: str
    score: float
    text: str
    source_title: str
    source_url: str
    chunk_index: int


class QueryResponse(BaseModel):
    question: str
    answer: str
    prompt: str
    chunks: list[ChunkInfo]
    retrieval_ms: int
    llm_ms: int


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(400, "Question must not be empty.")

    t0 = time.time()
    try:
        chunks = retrieve(req.question)
    except Exception as e:
        raise HTTPException(500, f"FTS retrieval failed: {e}")
    retrieval_ms = int((time.time() - t0) * 1000)

    t1 = time.time()
    try:
        answer, prompt = ask(req.question, chunks)
    except Exception as e:
        raise HTTPException(500, f"LLM call failed: {e}")
    llm_ms = int((time.time() - t1) * 1000)

    return QueryResponse(
        question=req.question,
        answer=answer,
        prompt=prompt,
        chunks=[ChunkInfo(**c) for c in chunks],
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
    )


@app.get("/api/n1ql")
async def n1ql(keyword: str = "index"):
    t0 = time.time()
    try:
        rows = n1ql_verify(keyword)
    except Exception as e:
        raise HTTPException(500, f"N1QL failed: {e}")
    return {"keyword": keyword, "rows": rows, "query_ms": int((time.time() - t0) * 1000)}


@app.get("/api/stats")
async def stats():
    try:
        cluster = get_cluster()
        total = next(iter(cluster.query(f"SELECT COUNT(*) AS n FROM `{COUCHBASE_BUCKET}`")))["n"]
    except Exception:
        total = -1
    return {
        "total_chunks": total,
        "bucket":       COUCHBASE_BUCKET,
        "scope":        COUCHBASE_SCOPE,
        "collection":   COUCHBASE_COLLECTION,
        "fts_index":    FTS_INDEX_NAME,
        "retrieval":    "Full-Text Search (BM25)",
        "llm_model":    OLLAMA_LLM_MODEL,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}
