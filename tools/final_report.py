"""최종 정리: 251개 채널 전체 영상을 같은 제목끼리 묶고, 묶음의 최고 조회수 순으로 번호를 매겨 txt/xlsx로 저장한다.

각 묶음 안에서는 업로드가 빠른 순서(먼저 올린 영상이 위)로 적는다.
채널 옆 표시: 🟢 최근 7일 안에 업로드 / 🟡 8~30일 / 🔴 30일 넘게 업로드 없음 (2026-10-29 기준)
"""
import csv, datetime, glob, json, os, re
from collections import Counter, defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

BASE = datetime.date(2026, 10, 29)
UNIT = {"초": 0, "분": 0, "시간": 0, "일": 1, "주": 7, "개월": 30, "년": 365}

an = list(csv.DictReader(open("channels/최종_채널분석.csv", encoding="utf-8-sig")))
keep = {}
for r in an:
    cid = r["채널링크"].rsplit("/", 1)[-1]
    keep[cid] = r
name_count = Counter(r["채널이름"] for r in an)


def label(r):
    n = r["채널이름"]
    return f"{n}(구독자 {r['구독자']})" if name_count[n] > 1 else n


def rel_days(s):
    m = re.search(r"(\d+)\s*(초|분|시간|일|주|개월|년)", s or "")
    return (int(m.group(1)) * UNIT[m.group(2)], m.group(2)) if m else (None, None)


def status(r):
    d, _ = rel_days(r["최근 업로드"])
    if d is None:
        return "⚪"
    return "🟢" if d <= 7 else ("🟡" if d <= 30 else "🔴")


def views(s):
    s = (s or "").replace("조회수", "").replace("회", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*(천|만|억)?", s)
    return int(round(float(m.group(1)) * {"천": 1e3, "만": 1e4, "억": 1e8, None: 1}[m.group(2)])) if m else 0


dates = json.load(open("channels/raw/_dates.json")) if os.path.exists("channels/raw/_dates.json") else {}
videos = []
for f in sorted(glob.glob("channels/raw/[0-9]*.json")):
    d = json.load(open(f, encoding="utf-8"))
    cid = d["info"].get("channel_id")
    if cid not in keep:
        continue
    ch = keep[cid]
    for v in d["videos"]:
        exact = dates.get(v["id"])
        dd, unit = rel_days(v["published"])
        if exact:
            day = datetime.date.fromisoformat(exact); approx = False
        elif dd is not None:
            day = BASE - datetime.timedelta(days=dd); approx = unit in ("주", "개월", "년")
        else:
            day, approx = None, True
        videos.append({"id": v["id"], "title": v["title"], "views": views(v["views"]), "day": day, "approx": approx,
                       "unit": unit, "channel": label(ch), "status": status(ch)})
print("videos", len(videos), "channels", len(keep))


def norm(t):
    t = re.sub(r"#\S+", "", t)
    t = re.sub(r"\[[^\]]*\]|【[^】]*】", "", t)
    # "ㅣ영상툰ㅣ썰툰…", "|채널명", "/사이다사연/…" 같은 태그 꼬리는 빼고 가장 긴 본문 조각만 비교한다
    parts = [p for p in re.split(r"[ㅣ|｜/]", t) if p.strip()]
    core = max(parts, key=len) if parts else t
    return re.sub(r"[^\w가-힣]", "", core).lower()


ns = [norm(v["title"]) for v in videos]
digits = [re.findall(r"\d+", n) for n in ns]
parent = list(range(len(videos)))


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x


first = {}
for i, n in enumerate(ns):
    if len(n) >= 10:
        if n in first:
            parent[find(i)] = find(first[n])
        else:
            first[n] = i
grams = [set(n[k:k + 4] for k in range(len(n) - 3)) for n in ns]
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
        # 숫자만 다른 연재물(#1/#2, 5편/6편)은 다른 제목으로 본다
        if digits[i] == digits[j] and len(s & grams[j]) / len(s | grams[j]) >= 0.65:
            parent[find(i)] = find(j)
groups = defaultdict(list)
for i in range(len(videos)):
    groups[find(i)].append(videos[i])
glist = sorted(groups.values(), key=lambda g: -max(v["views"] for v in g))
for g in glist:
    g.sort(key=lambda v: (v["day"] or datetime.date.max, -v["views"]))


def fdate(v):
    if not v["day"]:
        return "날짜 모름"
    d = v["day"]
    if v["approx"]:
        return f"{d.year}년 {d.month}월쯤" if v["unit"] in ("개월", "년") else f"{d.year}년 {d.month}월 {d.day}일쯤"
    return f"{d.year}년 {d.month}월 {d.day}일"


HEAD = [
    "251개 채널 전체 영상 제목 — 조회수 많이 나온 순서 (2026-10-29 기준)",
    "",
    "번호 순서: 같은 제목 묶음 안에서 가장 높은 조회수가 큰 순서",
    "묶음 안 순서: 먼저 올린 영상이 위 (업로드 날짜 빠른 순)",
    "같은 제목 기준: 태그·띄어쓰기·문장부호를 빼고 같거나, 글자의 65% 이상이 겹치는 제목",
    "채널 옆 표시: 🟢 최근 7일 안에 업로드(운영 중) / 🟡 8~30일 전 / 🔴 30일 넘게 업로드 없음",
    "날짜: 정확한 날짜는 그대로, YouTube가 'N개월 전'처럼만 보여 준 영상은 '쯤'으로 표시",
    "조회수: YouTube가 줄여 보여 주는 숫자(예: 4.5만)를 바꾼 값이라 대략적인 숫자",
    "쇼츠·라이브 제외 / 검색으로 새로 찾은 채널은 최근 영상 약 1,000개까지만 수집",
]


def write(path, only_dup):
    with open(path, "w", encoding="utf-8") as fp:
        sel = [g for g in glist if (len(g) > 1) or not only_dup]
        fp.write("\n".join(HEAD) + "\n")
        fp.write(f"\n총 {len(sel):,}개 제목 묶음 (영상 {sum(len(g) for g in sel):,}개)\n")
        for k, g in enumerate(sel, 1):
            fp.write(f"\n{k}. (중복횟수 총 {len(g)}회)\n" if len(g) > 1 else f"\n{k}. (중복 없음)\n")
            for v in g:
                fp.write(f"{v['title']}, {v['channel']}{v['status']}, {fdate(v)}, {v['views']:,}회\n")


write("channels/최종_전체제목_조회수순.txt", False)
write("channels/최종_중복제목만_조회수순.txt", True)

wb = Workbook()
ws = wb.active
ws.title = "조회수순 전체"
ws.append(["번호", "중복횟수", "영상 제목", "채널", "운영", "올린 날짜", "조회수", "영상 링크"])
for c in ws[1]:
    c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="E2EFDA")
gray = PatternFill("solid", fgColor="F2F2F2")
for k, g in enumerate(glist, 1):
    for v in g:
        ws.append([k, len(g), v["title"], v["channel"], v["status"], fdate(v), v["views"], "https://www.youtube.com/watch?v=" + v["id"]])
        row = ws.max_row
        ws.cell(row=row, column=7).number_format = "#,##0"
        ws.cell(row=row, column=8).hyperlink = ws.cell(row=row, column=8).value
for col, w in zip("ABCDEFGH", [8, 9, 100, 26, 6, 18, 12, 14]):
    ws.column_dimensions[col].width = w
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
wb.save("channels/최종_전체제목_조회수순.xlsx")
need = [v["id"] for g in glist if len(g) > 1 for v in g if v["approx"]]
json.dump(need, open("channels/raw/_need_dates.json", "w"))
print("need exact dates", len(need))
print("groups", len(glist), "dup groups", sum(1 for g in glist if len(g) > 1),
      "exact dates", sum(1 for v in videos if not v["approx"]), "approx", sum(1 for v in videos if v["approx"]))
