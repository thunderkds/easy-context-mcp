"""Spike 1: FastEmbed load. usage: spike1_fastembed.py <cache_dir> [download|offline]"""
import os, sys
cache, mode = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "offline"
if mode == "offline":
    os.environ["HF_HUB_OFFLINE"] = "1"
from fastembed import TextEmbedding
m = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=cache, threads=2)
v = list(m.embed(["hello"]))[0]
print("mode=%s dim=%d" % (mode, len(v)))
for root, _, fs in os.walk(cache):
    for f in fs:
        p = os.path.join(root, f)
        print(os.path.getsize(p), os.path.relpath(p, cache))
