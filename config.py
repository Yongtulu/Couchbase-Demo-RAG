# config.py — central configuration for the Couchbase RAG Demo

COUCHBASE_HOST       = "127.0.0.1"
COUCHBASE_USER       = "Administrator"
COUCHBASE_PASSWORD   = "your_password_here"   # update before running
COUCHBASE_BUCKET     = "rag_demo"
COUCHBASE_SCOPE      = "_default"
COUCHBASE_COLLECTION = "_default"

OLLAMA_BASE_URL      = "http://127.0.0.1:11434"
OLLAMA_LLM_MODEL     = "gemma4:e4b"

FTS_INDEX_NAME       = "chunk_fts_idx"

CHUNK_SIZE           = 400
CHUNK_OVERLAP        = 60
TOP_K                = 3

SITEMAP_URL = "https://docs.couchbase.com/sitemap-server.xml"

# sections to load from the sitemap
DOCS_SECTIONS = [
    "getting-started",
    "install",
    "introduction",
    "learn",
    "guides",
]
