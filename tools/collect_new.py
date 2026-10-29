"""검색으로 새로 찾은 채널의 영상을 수집한다 (채널당 최근 약 1,000개)."""
import json, sys
sys.path.insert(0, "tools")
from yt_scrape import channel_videos

disc = json.load(open("channels/raw/_discovered.json", encoding="utf-8"))
new = [r for r in disc if not r["known"] and r["n_sidae"] >= 2]
for k, r in enumerate(new):
    i = 1000 + k
    rec = {"list_name": r["name"], "list_category": "⑦ YouTube 검색으로 새로 발견", "input_link": "https://www.youtube.com/channel/" + r["channel_id"]}
    try:
        info, vids = channel_videos(rec["input_link"], max_pages=33)
        if info:
            rec.update(info)
            rec["channel_url"] = rec["input_link"]
            rec["status"] = "ok"; rec["n_collected"] = len(vids)
            json.dump({"info": rec, "videos": vids}, open(f"channels/raw/{i}.json", "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        rec["status"] = "오류 " + str(e)[:80]
    print(k, r["name"], rec.get("subscribers", ""), rec.get("n_collected", rec.get("status")), flush=True)
print("DONE")
