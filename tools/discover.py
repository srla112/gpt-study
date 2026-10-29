"""YouTube 검색으로 시댁 사연 채널을 새로 찾는다. 이미 수집한 채널은 제외한다."""
import glob, json, re, sys, time, urllib.parse
from collections import defaultdict
sys.path.insert(0, "tools")
from yt_scrape import get, initial_data, ytcfg, walk, text, continuation

QUERIES = [
    "시모 참교육", "시어머니 참교육 사연", "시누 참교육", "시누이 사연", "동서 참교육", "동서 사연",
    "시댁 참교육", "시댁식구 참교육", "시댁 사연 라디오", "시댁 사이다 사연", "며느리 참교육 사연",
    "고부갈등 사이다", "시모 막말 사연", "시댁 파멸", "시모 부재중 전화", "시댁 오디오북",
    "시모 무릎꿇고", "명절 시댁 사연", "제사 시모 사연", "산후조리 시모 사연", "시아버지 사연 며느리",
    "예비시모 사연", "상견례 시댁 사연", "시누 돌잔치 사연", "친정 무시 시모", "실화사연 시모",
    "신청사연 시모", "사연라디오 시댁", "반전사연 시모", "시댁 사연 몰아보기", "시모 인생 박살",
    "시댁식구들 벌벌", "시모 얼굴이 하얗게", "시누 인생 나락", "동서 얼굴이 하얗게 질리는데",
    "시댁 풍비박산", "시모 결제 취소", "시댁 돈줄 끊고", "며느리 정체 재벌 시댁", "시모 칠순 사연",
    "시댁 김장 사연", "합가 시모 사연", "시누 결혼식 사연", "시모 명의 사연", "시댁 유산 며느리 사연",
]
LONG = "EgIYAg%3D%3D"  # 길이 20분 이상 필터
PAGES = 5

known = set()
for f in glob.glob("channels/raw/[0-9]*.json"):
    cid = json.load(open(f, encoding="utf-8"))["info"].get("channel_id")
    if cid:
        known.add(cid)

hits = defaultdict(lambda: {"name": "", "videos": {}, "queries": set()})


def take(data, q):
    n = 0
    for v in walk(data, "videoRenderer"):
        owner = v.get("ownerText") or v.get("longBylineText") or {}
        runs = owner.get("runs") or [{}]
        cid = runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId")
        if not cid:
            continue
        h = hits[cid]
        h["name"] = runs[0].get("text", "")
        h["videos"][v.get("videoId")] = text(v.get("title"))
        h["queries"].add(q)
        n += 1
    return n


for q in QUERIES:
    try:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=" + LONG
        html = get(url)
        data = initial_data(html)
        key, ver = ytcfg(html)
        n = take(data, q)
        tok = continuation(data)
        for _ in range(PAGES - 1):
            if not tok:
                break
            body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver, "hl": "ko", "gl": "KR"}}, "continuation": tok}).encode()
            d = json.loads(get("https://www.youtube.com/youtubei/v1/search?prettyPrint=false" + (f"&key={key}" if key else ""), body))
            n += take(d, q)
            tok = continuation(d)
            time.sleep(0.3)
        print(q, n, len(hits), flush=True)
    except Exception as e:
        print(q, "오류", e, flush=True)

SIDAE = re.compile(r"시모|시어머니|시누|동서|시댁|시부|시아버지|시가|시월드|며느리|고부|형님|올케")
out = []
for cid, h in hits.items():
    titles = list(h["videos"].values())
    sid = sum(bool(SIDAE.search(t)) for t in titles)
    out.append({"channel_id": cid, "name": h["name"], "n_videos_found": len(titles), "n_sidae": sid,
                "n_queries": len(h["queries"]), "known": cid in known, "sample": titles[:3]})
out.sort(key=lambda r: (-r["n_sidae"], -r["n_queries"]))
json.dump(out, open("channels/raw/_discovered.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
new = [r for r in out if not r["known"] and r["n_sidae"] >= 2]
print("TOTAL", len(out), "NEW(시댁 제목 2개 이상)", len(new))
