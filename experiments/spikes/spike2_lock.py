"""Spike 2. usage: spike2_lock.py <dir> hold <secs> | try | wal-write | wal-read"""
import fcntl, os, sqlite3, sys, time
d, cmd = sys.argv[1], sys.argv[2]
lp = os.path.join(d, "write.lock"); db = os.path.join(d, "index.sqlite")
if cmd == "hold":
    f = open(lp, "a+"); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("HOLDING", flush=True); time.sleep(float(sys.argv[3]))
elif cmd == "try":
    f = open(lp, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); print("ACQUIRED")
    except BlockingIOError as e:
        print("BlockingIOError", e)
elif cmd == "wal-write":
    c = sqlite3.connect(db); print(c.execute("pragma journal_mode=wal").fetchone())
    c.execute("create table if not exists t(who text, n int)")
    for i in range(int(sys.argv[3])): c.execute("insert into t values(?,?)", (sys.argv[4], i))
    c.commit(); print("written", sys.argv[4])
elif cmd == "wal-read":
    c = sqlite3.connect(db)
    print(c.execute("select who,count(*),max(n) from t group by who").fetchall())
    print(c.execute("pragma integrity_check").fetchone())
