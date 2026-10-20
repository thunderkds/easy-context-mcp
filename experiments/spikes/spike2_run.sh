#!/usr/bin/env bash
# Spike 2 driver: flock + WAL across host and python:3.12-slim container on one bind mount.
S="$(cd "$(dirname "$0")" && pwd)"; D=${1:-/tmp/spike2}
rm -rf "$D"; mkdir -p "$D"; chmod 777 "$D"
ctr() { docker run --rm --user "$(id -u):$(id -g)" -v "$D:$D" -v "$S:/s:ro" python:3.12-slim python /s/spike2_lock.py "$@"; }
host() { python3 "$S/spike2_lock.py" "$@"; }
echo "== A: container holds, host tries"
docker run -d --name sp2 --user "$(id -u):$(id -g)" -v "$D:$D" -v "$S:/s:ro" python:3.12-slim python /s/spike2_lock.py "$D" hold 8 >/dev/null
sleep 2; host "$D" try; sleep 8; echo "(after release)"; host "$D" try; docker rm -f sp2 >/dev/null 2>&1
echo "== B: host holds, container tries"
host "$D" hold 8 & sleep 1; ctr "$D" try; wait; echo "(after release)"; ctr "$D" try
echo "== C: WAL host writes -> container reads -> container writes -> host reads"
host "$D" wal-write 500 host; ctr "$D" wal-read; ctr "$D" wal-write 500 container; host "$D" wal-read
echo "== D: concurrent writers, readers mid-write"
host "$D" wal-write 20000 hostbig & ctr "$D" wal-write 20000 ctrbig & sleep 0.7
echo "reader (container) mid-write:"; ctr "$D" wal-read; echo "reader (host) mid-write:"; host "$D" wal-read; wait
echo "final:"; host "$D" wal-read; ctr "$D" wal-read
