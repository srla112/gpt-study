"""웹페이지를 인터넷 없이도 열리는 한 개의 HTML 파일로 만든다 (데이터를 파일 안에 넣음)."""
import json, os, sys
D = os.environ.get("PROJ", "channels")
OUT = sys.argv[1] if len(sys.argv) > 1 else "channels/시댁사연_제목순위.html"

page = open(f"{D}/web/index.html", encoding="utf-8").read()
meta = open(f"{D}/web/meta.json", encoding="utf-8").read()
parts = [open(f"{D}/web/data-{n}.json", encoding="utf-8").read() for n in range(1, json.loads(meta)["parts"] + 1)]
loader_old = 'fetch("meta.json").then(function (r) { return r.json(); }).then(function (m) {'
loader_new = 'Promise.resolve(window.__META__).then(function (m) {'
part_old = 'return fetch("data-" + n + ".json").then(function (r) {\n      if (!r.ok) throw new Error(r.status);\n      return r.json();\n    }).then(function (part) {'
part_new = 'return Promise.resolve(window.__PARTS__[n - 1]).then(function (part) {'
assert loader_old in page and part_old in page
page = page.replace(loader_old, loader_new).replace(part_old, part_new)
data = "<script>window.__META__=" + meta + ";window.__PARTS__=[" + ",".join(parts) + "];</script>\n"
title_end = page.index("</title>") + len("</title>")
head, body = page[:title_end], page[title_end:]
style_end = body.index("</style>") + len("</style>")
out = ("<!doctype html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
       "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
       + head + body[:style_end] + "\n</head>\n<body>\n" + data + body[style_end:] + "\n</body>\n</html>\n")
open(OUT, "w", encoding="utf-8").write(out)
print(len(out.encode()) // 1024 // 1024, "MB")
