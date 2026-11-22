#!/usr/bin/env python3
"""Every 5th story (counted over the whole trip) is a live-tracking story; layouts A and B alternate.
State lives in the repo: stories/state.json {"count": N, "live_count": M}.
plan  : story_plan.py plan N      -> for the next N stories prints one line each: "<i> normal" or "<i> live A|B"
commit: story_plan.py commit N    -> after N stories were really posted, advance the counter (then git commit + push)
"""
import json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, "stories", "state.json")
st = json.load(open(P)) if os.path.exists(P) else {"count": 0, "live_count": 0}
cmd, n = sys.argv[1], int(sys.argv[2])
if cmd == "plan":
    c, lc = st["count"], st["live_count"]
    for i in range(1, n + 1):
        c += 1
        if c % 5 == 0:
            print(i, "live", "AB"[lc % 2]); lc += 1
        else:
            print(i, "normal")
elif cmd == "commit":
    for _ in range(n):
        st["count"] += 1
        if st["count"] % 5 == 0: st["live_count"] += 1
    os.makedirs(os.path.dirname(P), exist_ok=True); json.dump(st, open(P, "w"), indent=1); print(st)
