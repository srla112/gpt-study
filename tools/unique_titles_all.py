"""251개 채널 전체 영상과 비교해, 상 채널 영상 중 한 번도 겹치지 않는 제목만 채널별 조회수 순으로 txt에 정리한다."""
import csv, re
from collections import Counter, defaultdict


def norm(t):
    t = re.sub(r"#\S+", "", t)
    t = re.sub(r"\[[^\]]*\]|【[^】]*】", "", t)
    return re.sub(r"[^\w가-힣]", "", t).lower()


def views(s):
    s = (s or "").replace("조회수", "").replace("회", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*(천|만|억)?", s)
    return int(round(float(m.group(1)) * {"천": 1e3, "만": 1e4, "억": 1e8, None: 1}[m.group(2)])) if m else 0


rows = list(csv.DictReader(open("channels/전체_영상제목.csv", encoding="utf-8-sig")))
top = [r["채널이름"].replace(" ★기준", "") for r in csv.DictReader(open("channels/유사도_상.csv", encoding="utf-8-sig"))]
topset = set(top)
for r in rows:
    r["n"] = norm(r["제목"])
    r["v"] = views(r["조회수"])

exact = Counter(r["n"] for r in rows if len(r["n"]) >= 10)
grams = [set(r["n"][k:k + 4] for k in range(len(r["n"]) - 3)) for r in rows]
df = Counter(g for s in grams for g in s)
LIM = 250
inv = defaultdict(list)
for i, s in enumerate(grams):
    for g in s:
        if df[g] <= LIM:
            inv[g].append(i)
dup = [exact.get(r["n"], 0) > 1 for r in rows]
for i, s in enumerate(grams):
    if len(s) < 8:
        continue
    cnt = Counter(j for g in s if df[g] <= LIM for j in inv[g] if j != i)
    for j, c in cnt.most_common(50):
        if c < 5:
            break
        if len(s & grams[j]) / len(s | grams[j]) >= 0.65:
            dup[i] = dup[j] = True
            break

import datetime
BASE = datetime.date(2026, 10, 29)
an = {r["채널이름"]: r for r in csv.DictReader(open("channels/최종_채널분석.csv", encoding="utf-8-sig"))}


def last_upload(ch):
    r = an.get(ch, {})
    t = r.get("최근 업로드", "")
    m = re.search(r"(\d+)\s*(초|분|시간|일|주|개월|년)", t)
    if not m:
        return "최근 업로드 확인 못 함"
    d = int(m.group(1)) * {"초": 0, "분": 0, "시간": 0, "일": 1, "주": 7, "개월": 30, "년": 365}[m.group(2)]
    date = BASE - datetime.timedelta(days=d)
    approx = "" if m.group(2) in ("초", "분", "시간", "일") else "쯤"
    state = "🟢 운영 중" if d <= 7 else ("🟡 최근 한 달 안에 활동" if d <= 30 else "🔴 업로드 멈춤")
    return f"{state} · 최근 업로드 {t} ({date:%Y-%m-%d}{approx}) · 최근 30일 업로드 {r.get('최근 30일 업로드', '?')}개"


by = defaultdict(list)
for r, d in zip(rows, dup):
    if not d and r["채널이름"] in topset:
        by[r["채널이름"]].append(r)
total = sum(len(v) for v in by.values())
with open("channels/상_채널_중복없는_제목.txt", "w", encoding="utf-8") as fp:
    fp.write(f"상 채널 중복 없는 영상 제목 — 251개 채널 영상 {len(rows):,}개 전체와 비교해 한 번도 겹치지 않은 제목만 (총 {total:,}개)\n")
    fp.write("채널 순서: 기준 채널 → 구독자 많은 순 / 채널 안: 조회수 높은 순\n형식: 순위. 영상 제목 | 조회수\n")
    fp.write("운영 상태(2026-10-29 기준): 🟢 운영 중 = 최근 7일 안에 업로드 / 🟡 최근 한 달 안에 활동 = 8~30일 전 / 🔴 업로드 멈춤 = 30일 넘게 업로드 없음\n")
    fp.write("\n[채널 운영 상태 한눈에 보기]\n")
    for ch in top:
        if by.get(ch):
            fp.write(f"- {ch}: {last_upload(ch)}\n")
    for ch in top:
        items = sorted(by.get(ch, []), key=lambda r: -r["v"])
        if not items:
            continue
        fp.write(f"\n{'=' * 60}\n■ {ch} ({len(items)}개)\n  {last_upload(ch)}\n{'=' * 60}\n")
        for k, r in enumerate(items, 1):
            fp.write(f"{k}. {r['제목']} | {r['v']:,}회\n")
import collections
print(collections.Counter(last_upload(c).split(" · ")[0] for c in top if by.get(c)))
print(total, sum(1 for c in top if by.get(c)), {c: len(by.get(c, [])) for c in top[:2]})
