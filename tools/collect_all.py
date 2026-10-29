"""최종 채널 목록의 모든 채널을 방문해 채널 정보와 전체 영상 제목을 수집한다."""
import csv, json, re, sys, time, urllib.parse, traceback
sys.path.insert(0, "tools")
from yt_scrape import channel_videos, search_channel

SRC = "channels/최종_유사채널_목록.csv"
OUT = "channels/raw"
import os
os.makedirs(OUT, exist_ok=True)


def norm(s):
    return re.sub(r"[\s•·\-_:()（）\[\]'\"]", "", s or "").lower()


rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
results = []
for i, r in enumerate(rows):
    name = r["채널이름"].split(" (")[0]
    link = r["채널링크"]
    rec = {"list_name": r["채널이름"], "list_category": r["분류"], "input_link": link}
    try:
        if "results?" in link:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["search_query"][0]
            cands = search_channel(q)
            target = norm(name)
            pick = next((c for c in cands if norm(c["name"]) == target), None) or \
                   next((c for c in cands if target in norm(c["name"]) or norm(c["name"]) in target), None)
            rec["search_candidates"] = [c["name"] for c in cands[:5]]
            if not pick:
                rec["status"] = "검색으로 채널 못 찾음"
                results.append(rec); print(i, name, rec["status"], rec["search_candidates"], flush=True); continue
            link = "https://www.youtube.com/channel/" + pick["channel_id"]
            rec["matched_by_search"] = pick["name"]
        info, vids = channel_videos(link)
        if info is None:
            rec["status"] = "채널 페이지 읽기 실패"
        else:
            rec.update(info)
            rec["channel_url"] = "https://www.youtube.com/channel/" + info["channel_id"] if info.get("channel_id") else link
            rec["status"] = "ok"
            rec["n_collected"] = len(vids)
            json.dump({"info": rec, "videos": vids}, open(f"{OUT}/{i:03d}.json", "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        rec["status"] = "오류: " + str(e)[:100]
    results.append(rec)
    print(i, name, rec.get("status"), rec.get("name", ""), rec.get("subscribers", ""), rec.get("n_collected", ""), flush=True)
json.dump(results, open(f"{OUT}/_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE")
