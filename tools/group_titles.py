"""251개 채널 전체 영상(81,061개)을 같은/거의 같은 제목끼리 묶어 channels/raw/_groups.json에 저장한다."""
import csv, json, re
from collections import Counter, defaultdict


def norm(t):
    t = re.sub(r"#\S+", "", t)
    t = re.sub(r"\[[^\]]*\]|【[^】]*】", "", t)
    return re.sub(r"[^\w가-힣]", "", t).lower()


rows = list(csv.DictReader(open("channels/전체_영상제목.csv", encoding="utf-8-sig")))
ns = [norm(r["제목"]) for r in rows]
parent = list(range(len(rows)))


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
        if len(s & grams[j]) / len(s | grams[j]) >= 0.65:
            parent[find(i)] = find(j)
gid = [find(i) for i in range(len(rows))]
json.dump(gid, open("channels/raw/_groups.json", "w"))
sizes = Counter(gid)
dupv = [i for i in range(len(rows)) if sizes[gid[i]] > 1]
coarse = [i for i in dupv if re.search(r"주|개월|년", rows[i]["업로드"])]
print("groups", len(sizes), "dup groups", sum(1 for v in sizes.values() if v > 1), "videos in dup", len(dupv), "coarse dates among them", len(coarse))
