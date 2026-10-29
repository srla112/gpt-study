"""YouTube 채널의 영상 제목/조회수/길이/업로드 시점을 수집한다 (API 키 없이 웹 페이지 데이터 사용)."""
import json, re, sys, time, urllib.request, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HDR = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9", "Cookie": "CONSENT=YES+1; PREF=hl=ko&gl=KR"}


def get(url, data=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=dict(HDR, **({"Content-Type": "application/json"} if data else {})))
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def initial_data(html):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S) or re.search(r'ytInitialData"\]\s*=\s*(\{.*?\});', html, re.S)
    return json.loads(m.group(1)) if m else None


def ytcfg(html):
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    return (key.group(1) if key else None, ver.group(1) if ver else "2.20240101.00.00")


def walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, key)


def text(t):
    if not t:
        return ""
    if isinstance(t, str):
        return t
    if "simpleText" in t:
        return t["simpleText"]
    if "runs" in t:
        return "".join(r.get("text", "") for r in t["runs"])
    if "content" in t:
        return t["content"]
    return ""


def videos_from(data):
    out = []
    for v in walk(data, "videoRenderer"):
        out.append({
            "id": v.get("videoId"),
            "title": text(v.get("title")),
            "views": text(v.get("viewCountText")) or text(v.get("shortViewCountText")),
            "length": text(v.get("lengthText")),
            "published": text(v.get("publishedTimeText")),
        })
    for v in walk(data, "lockupViewModel"):
        if v.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
            continue
        meta = v.get("metadata", {}).get("lockupMetadataViewModel", {})
        rows = [text(p.get("text")) for p in walk(meta, "metadataParts") for p in (p if isinstance(p, list) else [p])]
        length = next((text(b.get("text")) for b in walk(v, "thumbnailBadgeViewModel")), "")
        out.append({"id": v.get("contentId"), "title": text(meta.get("title")), "views": rows[0] if rows else "",
                    "length": length, "published": rows[1] if len(rows) > 1 else ""})
    return out


def continuation(data):
    for c in walk(data, "continuationCommand"):
        if c.get("token"):
            return c["token"]
    return None


def channel_header(data):
    info = {}
    md = next(walk(data, "channelMetadataRenderer"), {})
    info["name"] = md.get("title", "")
    info["channel_id"] = md.get("externalId", "")
    info["description"] = md.get("description", "")
    vanity = md.get("vanityChannelUrl", "") or ""
    info["handle"] = vanity.rsplit("/", 1)[-1] if "@" in vanity else ""
    parts = []
    for p in walk(data, "metadataParts"):
        for x in p if isinstance(p, list) else [p]:
            parts.append(text(x.get("text")))
    for p in parts:
        if "구독자" in p or "subscriber" in p:
            info["subscribers"] = p
        if "동영상" in p or "videos" in p:
            info["video_count"] = p
    sub = next(walk(data, "subscriberCountText"), None)
    if sub and "subscribers" not in info:
        info["subscribers"] = text(sub)
    return info


def channel_videos(url, max_pages=200):
    base = url.split("?")[0].rstrip("/")
    base = re.sub(r"/(videos|featured|about|streams|shorts)$", "", base)
    html = get(base + "/videos")
    data = initial_data(html)
    if not data:
        return None, []
    info = channel_header(data)
    key, ver = ytcfg(html)
    vids = videos_from(data)
    tok = continuation(data)
    pages = 0
    while tok and pages < max_pages:
        body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver, "hl": "ko", "gl": "KR"}}, "continuation": tok}).encode()
        d = json.loads(get("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false" + (f"&key={key}" if key else ""), body))
        new = videos_from(d)
        if not new:
            break
        vids += new
        tok = continuation(d)
        pages += 1
        time.sleep(0.3)
    seen, uniq = set(), []
    for v in vids:
        if v["id"] and v["id"] not in seen:
            seen.add(v["id"])
            uniq.append(v)
    return info, uniq


def search_channel(name):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(name) + "&sp=EgIQAg%3D%3D"
    data = initial_data(get(url))
    res = []
    for c in walk(data, "channelRenderer"):
        res.append({"channel_id": c.get("channelId"), "name": text(c.get("title")),
                    "handle": text(c.get("subscriberCountText")) if text(c.get("subscriberCountText")).startswith("@") else "",
                    "subscribers": text(c.get("videoCountText")) if text(c.get("subscriberCountText")).startswith("@") else text(c.get("subscriberCountText"))})
    return res


if __name__ == "__main__":
    info, vids = channel_videos(sys.argv[1], max_pages=int(sys.argv[2]) if len(sys.argv) > 2 else 200)
    print(json.dumps(info, ensure_ascii=False))
    print(len(vids))
    for v in vids[:5]:
        print(v)
