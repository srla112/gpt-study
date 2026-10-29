"""같은 제목 묶음에 속한 영상 중 날짜가 대략적인 영상의 정확한 업로드 날짜를 가져온다 (이어받기 가능)."""
import csv, json, os, re, sys, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "tools")
from yt_scrape import get

D = os.environ.get("PROJ", "channels")
CACHE = f"{D}/raw/_dates.json"
if len(sys.argv) > 1:
    ids = []
else:
    rows = list(csv.DictReader(open("channels/전체_영상제목.csv", encoding="utf-8-sig")))
    gid = json.load(open("channels/raw/_groups.json"))
    sizes = Counter(gid)
    ids = [r["영상 링크"].split("v=")[1] for i, r in enumerate(rows) if sizes[gid[i]] > 1 and re.search(r"주|개월|년", r["업로드"])]
if len(sys.argv) > 1:  # final_report.py가 남긴 목록으로 추가 수집
    ids = json.load(open(sys.argv[1]))
dates = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
todo = [v for v in dict.fromkeys(ids) if v not in dates]
print("need", len(ids), "todo", len(todo), flush=True)
lock = threading.Lock()
done = [0]


def one(vid):
    body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": "2.20241001.00.00", "hl": "ko", "gl": "KR"}}, "videoId": vid}).encode()
    try:
        r = get("https://www.youtube.com/youtubei/v1/next?prettyPrint=false", body)
        m = re.search(r'"dateText":\{"simpleText":"[^"]*?(\d{4})\. (\d{1,2})\. (\d{1,2})\.', r)
        val = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    except Exception:
        val = None
    with lock:
        if val is not None:
            dates[vid] = val
        done[0] += 1
        if done[0] % 500 == 0:
            json.dump(dates, open(CACHE, "w"))
            print(done[0], len(dates), time.strftime("%H:%M:%S"), flush=True)


with ThreadPoolExecutor(6) as ex:
    list(ex.map(one, todo))
json.dump(dates, open(CACHE, "w"))
print("DONE", len(dates), sum(1 for v in dates.values() if v), flush=True)
