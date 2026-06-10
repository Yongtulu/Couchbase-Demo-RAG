# setup_couchbase.py — create bucket, collection, GSI index, and FTS index
#
# Run ONCE before ingest.py:
#   python setup_couchbase.py
#
# Couchbase Community Edition 8.0.1 supports:
#   - JSON document storage
#   - N1QL / SQL++ queries (GSI indexes)
#   - Full-Text Search (FTS) with BM25 ranking
#
# Vector Search is Enterprise Edition only — this demo uses FTS instead.

import time
import requests
from datetime import timedelta

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.management.buckets import CreateBucketSettings, BucketType
from couchbase.exceptions import BucketAlreadyExistsException, CouchbaseException

from config import (
    COUCHBASE_HOST, COUCHBASE_USER, COUCHBASE_PASSWORD,
    COUCHBASE_BUCKET, COUCHBASE_SCOPE, COUCHBASE_COLLECTION,
    FTS_INDEX_NAME,
)

AUTH = (COUCHBASE_USER, COUCHBASE_PASSWORD)


def connect():
    auth = PasswordAuthenticator(COUCHBASE_USER, COUCHBASE_PASSWORD)
    cluster = Cluster(f"couchbase://{COUCHBASE_HOST}", ClusterOptions(auth))
    cluster.wait_until_ready(timedelta(seconds=15))
    return cluster


def create_bucket(cluster):
    try:
        cluster.buckets().create_bucket(
            CreateBucketSettings(
                name=COUCHBASE_BUCKET,
                bucket_type=BucketType.COUCHBASE,
                ram_quota_mb=512,
            )
        )
        print(f"  Bucket '{COUCHBASE_BUCKET}' created.")
        time.sleep(3)
    except BucketAlreadyExistsException:
        print(f"  Bucket '{COUCHBASE_BUCKET}' already exists — skipping.")


def create_collection(cluster):
    cm = cluster.bucket(COUCHBASE_BUCKET).collections()
    try:
        from couchbase.management.collections import CollectionSpec
        cm.create_collection(
            CollectionSpec(COUCHBASE_COLLECTION, scope_name=COUCHBASE_SCOPE)
        )
        print(f"  Collection '{COUCHBASE_COLLECTION}' created.")
        time.sleep(2)
    except CouchbaseException as e:
        if "already exists" in str(e).lower():
            print(f"  Collection '{COUCHBASE_COLLECTION}' already exists — skipping.")
        else:
            raise


def create_primary_index(cluster):
    try:
        cluster.query(
            f"CREATE PRIMARY INDEX IF NOT EXISTS ON `{COUCHBASE_BUCKET}` USING GSI"
        ).execute()
        print("  Primary GSI index created.")
    except Exception as e:
        print(f"  Primary index note: {e}")


def create_fts_index():
    """
    Create a Full-Text Search index on the 'text' field using the English analyzer.
    This gives BM25-ranked keyword retrieval — the retrieval backbone of this RAG demo.
    """
    index_def = {
        "name": FTS_INDEX_NAME,
        "type": "fulltext-index",
        "params": {
            "mapping": {
                "types": {
                    f"{COUCHBASE_SCOPE}.{COUCHBASE_COLLECTION}": {
                        "enabled": True,
                        "dynamic": False,
                        "properties": {
                            "text": {
                                "enabled": True,
                                "fields": [
                                    {
                                        "name": "text",
                                        "type": "text",
                                        "store": True,
                                        "index": True,
                                        "analyzer": "en",
                                    }
                                ],
                            },
                            "source_title": {
                                "enabled": True,
                                "fields": [
                                    {
                                        "name": "source_title",
                                        "type": "text",
                                        "store": True,
                                        "index": True,
                                    }
                                ],
                            },
                            "source_url": {
                                "enabled": True,
                                "fields": [
                                    {"name": "source_url", "type": "text", "store": True}
                                ],
                            },
                            "chunk_index": {
                                "enabled": True,
                                "fields": [
                                    {"name": "chunk_index", "type": "number", "store": True}
                                ],
                            },
                        },
                    }
                },
                "default_mapping": {"enabled": False},
                "default_type": "_default",
                "default_analyzer": "standard",
            },
            "store": {"indexType": "scorch"},
        },
        "sourceType": "gocbcore",
        "sourceName": COUCHBASE_BUCKET,
        "planParams": {"maxPartitionsPerPIndex": 1024, "indexPartitions": 1},
    }

    url = (
        f"http://{COUCHBASE_HOST}:8094/api/bucket/{COUCHBASE_BUCKET}"
        f"/scope/{COUCHBASE_SCOPE}/index/{FTS_INDEX_NAME}"
    )
    resp = requests.put(url, json=index_def, auth=AUTH, timeout=30)
    if resp.status_code in (200, 201):
        print(f"  FTS index '{FTS_INDEX_NAME}' created.")
    elif "already exists" in resp.text.lower():
        print(f"  FTS index '{FTS_INDEX_NAME}' already exists — skipping.")
    else:
        print(f"  FTS API {resp.status_code}: {resp.text[:300]}")


def main():
    print("=== Couchbase RAG Demo — Setup ===\n")

    print("Step 1: Connecting...")
    cluster = connect()
    print("  Connected.\n")

    print("Step 2: Creating bucket...")
    create_bucket(cluster)
    print()

    print("Step 3: Creating collection...")
    create_collection(cluster)
    print()

    print("Step 4: Creating primary GSI index (for N1QL)...")
    create_primary_index(cluster)
    print()

    print("Step 5: Creating Full-Text Search index...")
    create_fts_index()
    print()

    print("=== Setup complete. Run: python ingest.py ===")


if __name__ == "__main__":
    main()
