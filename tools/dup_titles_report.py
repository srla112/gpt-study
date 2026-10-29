"""상 채널 영상 중 다른 영상과 겹치는 제목을 채널별로 모아, 같은 제목 영상들 중 가장 최근 업로드와 최고 조회수를 txt에 정리한다."""
import csv, datetime, re
from collections import Counter, defaultdict

BASE = datetime.date(2026, 10, 29)


def norm(t):
    t = re.sub(r"#\S+", "", t)
    t = re.sub(r"\[[^\]]*\]|【[^】]*】", "", t)
    return re.sub(r"[^\w가-힣]", "", t).lower()


def views(s):
    s = (s or "").replace("조회수", "").replace("회", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*(천|만|억)?", s)
    return int(round(float(m.group(1)) * {"천": 1e3, "만": 1e4, "억": 1e8, None: 1}[m.group(2)])) if m else 0


def days(s):
    m = re.search(r"(\d+)\s*(초|분|시간|일|주|개월|년)", s or "")
    return int(m.group(1)) * {"초": 0, "분": 0, "시간": 0, "일": 1, "주": 7, "개월": 30, "년": 365}[m.group(2)] if m else 99999


def when(s):
    d = days(s)
    if d == 99999:
        return "날짜 확인 못 함"
    date = BASE - datetime.timedelta(days=d)
    return f"{s} ({date:%Y-%m-%d}{'' if re.search(r'초|분|시간|일', s) else '쯤'})"


rows = list(csv.DictReader(open("channels/전체_영상제목.csv", encoding="utf-8-sig")))
top = [r["채널이름"].replace(" ★기준", "") for r in csv.DictReader(open("channels/유사도_상.csv", encoding="utf-8-sig"))]
for r in rows:
    r["n"] = norm(r["제목"]); r["v"] = views(r["조회수"]); r["d"] = days(r["업로드"])

parent = list(range(len(rows)))


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x


first = {}
for i, r in enumerate(rows):
    if len(r["n"]) >= 10:
        if r["n"] in first:
            parent[find(i)] = find(first[r["n"]])
        else:
            first[r["n"]] = i
grams = [set(r["n"][k:k + 4] for k in range(len(r["n"]) - 3)) for r in rows]
df = Counter(g for s in grams for g in s)
LIM = 250
inv = defaultdict(list)
for i, s in enumerate(grams):
    for g in s:
        if df[g] <= LIM:
            inv[g].append(i)
for i, s in enumerate(grams):
    if len(s) < 8:
        continue
    cnt = Counter(j for g in s if df[g] <= LIM for j in inv[g] if j > i)
    for j, c in cnt.most_common(50):
        if c < 5:
            break
        if len(s & grams[j]) / len(s | grams[j]) >= 0.65:
            parent[find(i)] = find(j)
groups = defaultdict(list)
for i in range(len(rows)):
    groups[find(i)].append(i)

with open("channels/상_채널_중복제목_최근날짜_최고조회수.txt", "w", encoding="utf-8") as fp:
    fp.write("상 채널 영상 중 다른 영상과 제목이 겹치는 영상 (251개 채널 영상 81,061개와 비교)\n")
    fp.write("채널 순서: 기준 채널 → 구독자 많은 순 / 채널 안: 같은 제목 영상들의 최고 조회수 높은 순\n")
    fp.write("각 항목: 제목 / 이 채널 조회수 / 같은 제목 영상 수 / 가장 최근 업로드(채널) / 최고 조회수(채널)\n")
    fp.write("날짜는 2026-10-29 기준, 한 달이 넘으면 YouTube 표시가 대략적이라 '쯤'으로 적었습니다.\n")
    total = 0
    for ch in top:
        mine = [i for i, r in enumerate(rows) if r["채널이름"] == ch and len(groups[find(i)]) > 1]
        seen, items = set(), []
        for i in mine:
            g = find(i)
            if g in seen:
                continue
            seen.add(g)
            members = [rows[k] for k in groups[g]]
            own = max((m for m in members if m["채널이름"] == ch), key=lambda m: m["v"])
            recent = min(members, key=lambda m: m["d"])
            best = max(members, key=lambda m: m["v"])
            items.append((best["v"], own, len(members), len({m["채널이름"] for m in members}), recent, best))
        if not items:
            continue
        items.sort(key=lambda x: -x[0])
        total += len(items)
        fp.write(f"\n{'=' * 70}\n■ {ch} (겹치는 제목 {len(items)}개)\n{'=' * 70}\n")
        for k, (bv, own, n, nch, recent, best) in enumerate(items, 1):
            fp.write(f"{k}. {own['제목']}\n")
            fp.write(f"   - 이 채널 조회수: {own['v']:,}회 · 같은 제목 영상 {n}개 (채널 {nch}곳)\n")
            fp.write(f"   - 가장 최근 업로드: {when(recent['업로드'])} · {recent['채널이름']}\n")
            fp.write(f"   - 최고 조회수: {best['v']:,}회 · {best['채널이름']}\n")
print("items", total)
