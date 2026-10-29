"""사연: 기준 채널(세상만사·사연만남)과 정말 같은 형식인지 엄격하게 다시 거른다.

조건 (채널 영상 제목 기준):
  1) 시댁 인물(시모·시누·동서·시댁·시부 등) 제목 비율 50% 이상  — '며느리'만 있는 시어머니 시점 노후사연은 제외
  2) 1시간 넘는 영상 비율 50% 이상
  3) 따옴표 막말("…") 비율 40% 이상
  4) 복수 예고 문구(참교육·파멸·박살·무릎·질리는데·부재중 전화 등) 비율 40% 이상
"""
import csv, glob, json, re

SIDAE = re.compile(r"시모|시어머니|시어머님|시누|시동생|동서|시댁|시부|시아버지|시아버님|시가|시월드|시집")
QUOTE = re.compile(r"[\"“”'‘’].{2,}?[\"“”'‘’]")
TEASE = re.compile(r"참교육|파멸|박살|나락|무릎|오열|질리|풍비박산|쑥대밭|초토화|발칵|벌벌|쓰러지|부재중|결제|끊었|끊어|후회|최후|역관광|통곡|기절|애원|싹싹|뒤집|기겁|경악|하얗게|파랗게|사색|쫓겨|내쫓|퇴출|절연|연 끊|이혼서류|빈손")
an = {r["채널링크"]: r for r in csv.DictReader(open("channels/최종_채널분석.csv", encoding="utf-8-sig"))}


def secs(s):
    t = 0
    for x in (s or "").split(":"):
        if x.isdigit():
            t = t * 60 + int(x)
    return t


rows = []
for f in glob.glob("channels/raw/[0-9]*.json"):
    d = json.load(open(f, encoding="utf-8"))
    link = "https://www.youtube.com/channel/" + (d["info"].get("channel_id") or "")
    if link not in an:
        continue
    v = d["videos"]
    n = len(v)
    if not n:
        continue
    L = [secs(x["length"]) for x in v if x["length"]]
    r = an[link]
    rows.append({
        "name": r["채널이름"], "link": link, "subs": r["구독자"], "n": n, "base": r["유사도"] == "기준 채널",
        "sidae": sum(bool(SIDAE.search(x["title"])) for x in v) / n,
        "long": sum(1 for s in L if s >= 3600) / len(L) if L else 0,
        "quote": sum(bool(QUOTE.search(x["title"])) for x in v) / n,
        "tease": sum(bool(TEASE.search(x["title"])) for x in v) / n,
        "last": r["최근 업로드"], "grade": r["유사도"], "sample": v[0]["title"],
    })
ok = lambda r: r["sidae"] >= 0.5 and r["long"] >= 0.5 and r["quote"] >= 0.4 and r["tease"] >= 0.4
keep = [r for r in rows if r["base"] or ok(r)]
drop = [r for r in rows if not (r["base"] or ok(r))]
json.dump({"keep": [r["link"] for r in keep]}, open("channels/raw/_strict_keep.json", "w"))
print("기준 채널 값")
for r in rows:
    if r["base"]:
        print(f"  {r['name']}: 시댁 {r['sidae']:.0%} 롱폼 {r['long']:.0%} 따옴표 {r['quote']:.0%} 복수예고 {r['tease']:.0%}")
print("남는 채널", len(keep), "빠지는 채널", len(drop))
for r in sorted(keep, key=lambda r: (not r["base"], -float(re.sub(r'[^\d.]', '', r['subs'] or '0') or 0) * (10000 if '만' in r['subs'] else 1000 if '천' in r['subs'] else 1))):
    print(f"{r['name']} | {r['subs']} | 시댁 {r['sidae']:.0%} 롱폼 {r['long']:.0%} 따옴표 {r['quote']:.0%} 복수 {r['tease']:.0%} | 최근 {r['last']} | {r['sample'][:60]}")
