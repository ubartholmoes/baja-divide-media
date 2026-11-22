#!/usr/bin/env python3
"""Build Windsor.ai params for Instagram from a published media folder in ubartholmoes/baja-divide-media.

post : payload.py post  <folder> [--caption caption.txt]   -> ONE create_carousel_post params object
                 (video files first, then images, max 10; every item tagged with the 6 partner handles)
story: payload.py story <folder>                             -> LIST of create_story params objects (one per file, sorted)
Files are referenced as https://raw.githubusercontent.com/ubartholmoes/baja-divide-media/main/<folder>/<file>.
"""
import json, os, sys
KIT = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(KIT)
BASE = "https://raw.githubusercontent.com/ubartholmoes/baja-divide-media/main/"
T = json.load(open(os.path.join(KIT, "tags.json")))
kind, folder = sys.argv[1], sys.argv[2].strip("/")
files = sorted(f for f in os.listdir(os.path.join(REPO, folder)) if f.lower().endswith((".jpg", ".jpeg", ".mp4", ".mov")))
url = lambda f: BASE + folder + "/" + f
is_vid = lambda f: f.lower().endswith((".mp4", ".mov"))
def img_tags(pos): return [{"username": h, "x": x, "y": y} for h, (x, y) in zip(T["handles"], pos)]
vid_tags = [{"username": h} for h in T["handles"]]
if kind == "post":
    cap = open(sys.argv[sys.argv.index("--caption") + 1] if "--caption" in sys.argv else os.path.join(REPO, folder, "caption.txt"), encoding="utf-8").read().strip()
    order = [f for f in files if is_vid(f)] + [f for f in files if not is_vid(f)]
    if len(order) > 10: sys.exit(f"{len(order)} items – carousel allows max 10")
    items = [{"video_url": url(f), "user_tags": vid_tags} if is_vid(f) else {"image_url": url(f), "user_tags": img_tags(T["image_positions"])} for f in order]
    print(json.dumps({"caption": cap, "items": items}, ensure_ascii=False, indent=1))
elif kind == "story":
    out = [({"video_url": url(f), "user_tags": vid_tags} if is_vid(f) else {"image_url": url(f), "user_tags": img_tags(T["story_positions"])}) for f in files]
    print(json.dumps(out, ensure_ascii=False, indent=1))
else:
    sys.exit("kind must be post or story")
