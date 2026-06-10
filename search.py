# search.py — retrieve relevant chunks using Couchbase FTS REST API

import requests
from datetime import timedelta

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator

from config import (
    COUCHBASE_HOST, COUCHBASE_USER, COUCHBASE_PASSWORD,
    COUCHBASE_BUCKET, COUCHBASE_SCOPE,
    FTS_INDEX_NAME, TOP_K,
)

AUTH = (COUCHBASE_USER, COUCHBASE_PASSWORD)
FTS_URL = f"http://{COUCHBASE_HOST}:8094/api/bucket/{COUCHBASE_BUCKET}/scope/{COUCHBASE_SCOPE}/index/{FTS_INDEX_NAME}/query"


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Query Couchbase FTS via REST API, then fetch full document content via KV.
    Returns top_k chunks ranked by BM25 relevance.
    """
    # step 1: FTS to get matching doc IDs and scores
    resp = requests.post(
        FTS_URL,
        auth=AUTH,
        json={"query": {"query": query}, "size": top_k},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("hits") or []

    if not hits:
        return []

    # step 2: fetch full documents from Couchbase KV
    auth = PasswordAuthenticator(COUCHBASE_USER, COUCHBASE_PASSWORD)
    cluster = Cluster(f"couchbase://{COUCHBASE_HOST}", ClusterOptions(auth))
    cluster.wait_until_ready(timedelta(seconds=10))
    collection = cluster.bucket(COUCHBASE_BUCKET).default_collection()

    results = []
    for hit in hits:
        doc_id = hit["id"]
        score = round(hit["score"], 4)
        try:
            doc = collection.get(doc_id).content_as[dict]
            results.append({
                "id":           doc_id,
                "score":        score,
                "text":         doc.get("text", ""),
                "source_title": doc.get("source_title", ""),
                "source_url":   doc.get("source_url", ""),
                "chunk_index":  int(doc.get("chunk_index", 0)),
            })
        except Exception as e:
            print(f"  [KV ERROR] {doc_id}: {e}")

    return results


def n1ql_verify(keyword: str, limit: int = 5) -> list[dict]:
    """
    N1QL query to verify documents exist in Couchbase — used by the debug panel.
    """
    auth = PasswordAuthenticator(COUCHBASE_USER, COUCHBASE_PASSWORD)
    cluster = Cluster(f"couchbase://{COUCHBASE_HOST}", ClusterOptions(auth))
    cluster.wait_until_ready(timedelta(seconds=10))

    sql = f"""
        SELECT META().id  AS doc_id,
               source_title,
               chunk_index,
               SUBSTR(text, 0, 120) AS preview
        FROM   `{COUCHBASE_BUCKET}`
        WHERE  CONTAINS(LOWER(text), LOWER($keyword))
        ORDER  BY chunk_index
        LIMIT  {limit}
    """
    rows = []
    for row in cluster.query(sql, keyword=keyword):
        rows.append(row)
    return rows
