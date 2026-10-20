"""Build-time fetch of the embedding model into FASTEMBED_CACHE_PATH (baked into the image)."""

import os
import sys

from fastembed import TextEmbedding

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"  # keep equal to easy_context_mcp.embedding


def main() -> None:
    cache = os.environ.get("FASTEMBED_CACHE_PATH")
    if not cache:
        sys.exit("download_model: FASTEMBED_CACHE_PATH must be set")
    model = TextEmbedding(MODEL_ID, cache_dir=cache)
    dim = len(next(iter(model.embed(["warm up"]))))
    print(f"model {MODEL_ID} cached in {cache}, dim={dim}")


if __name__ == "__main__":
    main()
