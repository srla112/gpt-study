"""수집 실패하거나 동명이인 채널이 잡힌 항목을 다시 수집한다."""
import json, re, sys, urllib.parse
sys.path.insert(0, "tools")
from yt_scrape import channel_videos, search_channel

OUT = "channels/raw"
idx = json.load(open(f"{OUT}/_index.json", encoding="utf-8"))


def num(s):
    m = re.search(r"([\d.]+)\s*(천|만)?", s or "")
    return float(m.group(1)) * {"천": 1e3, "만": 1e4, None: 1}[m.group(2)] if m else 0


def norm(s):
    return re.sub(r"[\s•·\-_:()'\"]", "", s or "").lower()


def best(query, names):
    cands = search_channel(query)
    ok = [c for c in cands if any(norm(n) in norm(c["name"]) or norm(c["name"]) in norm(n) for n in names)]
    return max(ok, key=lambda c: num(c["subscribers"])) if ok else None, [c["name"] for c in cands[:5]]


# 번호: (직접 링크 또는 None, 검색어, 허용 이름들)
todo = {
    3: ("https://www.youtube.com/channel/UCXwBhLpVZQOfBid9_h-FMrA", None, None),
    8: (None, "사연모아", ["사연모아"]),
    11: (None, "깡냉이톡썰", ["깡냉이톡썰", "깡냉이"]),
    17: (None, "낭만캐스터", ["낭만캐스터"]),
    20: (None, "시월드 참교육 라디오", ["시월드참교육라디오", "시월드 참교육"]),
    25: (None, "막장해결사 사이다", ["막장해결사"]),
    30: (None, "사이다썰TV", ["사이다썰TV", "사이다썰"]),
    40: (None, "인생잔향", ["인생잔향"]),
    52: ("https://www.youtube.com/channel/UCbxDgHuiHjLXx83NL88tOig", None, None),
    57: (None, "사연극장 반전사연", ["사연극장"]),
    63: (None, "한수연의 사연 채널", ["한수연"]),
    68: (None, "앨리스몽 사연라디오", ["앨리스몽"]),
    74: (None, "썰모아 사연", ["썰모아"]),
}
for i, (link, q, names) in todo.items():
    rec = idx[i]
    try:
        if not link:
            pick, cands = best(q, names)
            rec["search_candidates"] = cands
            if not pick:
                rec["status"] = "검색으로 채널 못 찾음"; print(i, q, rec["status"], cands, flush=True); continue
            link = "https://www.youtube.com/channel/" + pick["channel_id"]
        info, vids = channel_videos(link)
        if info is None:
            rec["status"] = "채널 페이지 읽기 실패"; print(i, rec["status"], flush=True); continue
        for k in ("name", "channel_id", "description", "handle", "subscribers", "video_count"):
            rec.pop(k, None)
        rec.update(info)
        rec["channel_url"] = "https://www.youtube.com/channel/" + info["channel_id"]
        rec["status"] = "ok"; rec["n_collected"] = len(vids)
        json.dump({"info": rec, "videos": vids}, open(f"{OUT}/{i:03d}.json", "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        rec["status"] = "오류: " + str(e)[:100]
    print(i, rec.get("status"), rec.get("name", ""), rec.get("subscribers", ""), rec.get("n_collected", ""), flush=True)
json.dump(idx, open(f"{OUT}/_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
