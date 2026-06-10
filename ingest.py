# ingest.py — fetch Couchbase docs from sitemap, chunk, and store in Couchbase
#
# Usage:  python ingest.py
#
# Supports resume: already-stored doc IDs are skipped automatically.

import hashlib
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import timedelta

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import CouchbaseException, DocumentExistsException

from config import (
    COUCHBASE_HOST, COUCHBASE_USER, COUCHBASE_PASSWORD,
    COUCHBASE_BUCKET, COUCHBASE_SCOPE, COUCHBASE_COLLECTION,
    CHUNK_SIZE, CHUNK_OVERLAP,
    SITEMAP_URL, DOCS_SECTIONS,
)


def connect():
    auth = PasswordAuthenticator(COUCHBASE_USER, COUCHBASE_PASSWORD)
    cluster = Cluster(f"couchbase://{COUCHBASE_HOST}", ClusterOptions(auth))
    cluster.wait_until_ready(timedelta(seconds=10))
    collection = cluster.bucket(COUCHBASE_BUCKET).default_collection()
    return collection


def get_urls_from_sitemap() -> list[str]:
    """Fetch sitemap and return URLs matching selected sections."""
    print("Fetching sitemap...")
    r = requests.get(SITEMAP_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml-xml")
    all_urls = [loc.text for loc in soup.find_all("loc") if "server/current" in loc.text]

    selected = []
    for url in all_urls:
        path = url.replace("https://docs.couchbase.com/server/current/", "")
        section = path.split("/")[0]
        if section in DOCS_SECTIONS:
            selected.append(url)

    print(f"Found {len(selected)} pages across {len(DOCS_SECTIONS)} sections.\n")
    return selected


def fetch_text(url: str) -> tuple[str, str]:
    headers = {"User-Agent": "CouchbaseRAGDemo/1.0"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(separator=" ", strip=True) if main else ""
    text = " ".join(text.split())
    return title, text


def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def make_doc_id(url: str, idx: int) -> str:
    return f"chunk_{hashlib.md5(url.encode()).hexdigest()[:8]}_{idx:04d}"


def ingest():
    print("Connecting to Couchbase...")
    collection = connect()
    print("Connected.\n")

    urls = get_urls_from_sitemap()
    total_stored = 0
    total_skipped = 0

    for url in tqdm(urls, desc="Pages"):
        try:
            title, text = fetch_text(url)
        except Exception as e:
            tqdm.write(f"  [SKIP] {url} — {e}")
            continue

        if len(text) < 100:
            continue

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            doc_id = make_doc_id(url, i)
            # skip if already stored (resume support)
            try:
                collection.get(doc_id)
                total_skipped += 1
                continue
            except Exception:
                pass

            doc = {
                "text":         chunk,
                "source_url":   url,
                "source_title": title,
                "chunk_index":  i,
                "ingested_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            try:
                collection.upsert(doc_id, doc)
                total_stored += 1
            except CouchbaseException as e:
                tqdm.write(f"  [CB ERROR] {doc_id}: {e}")

        time.sleep(0.1)  # be gentle on the network

    print(f"\nDone. Stored: {total_stored}  Skipped (already exist): {total_skipped}")


if __name__ == "__main__":
    ingest()
