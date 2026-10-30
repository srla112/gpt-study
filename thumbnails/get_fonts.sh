#!/bin/sh
# 썸네일 렌더링용 폰트(OFL)를 fonts/ 에 받는다
cd "$(dirname "$0")" && mkdir -p fonts && B=https://raw.githubusercontent.com/google/fonts/main/ofl
curl -sSL -o fonts/EastSeaDokdo-Regular.ttf $B/eastseadokdo/EastSeaDokdo-Regular.ttf
curl -sSL -o fonts/BlackHanSans-Regular.ttf $B/blackhansans/BlackHanSans-Regular.ttf
curl -sSL -o fonts/SongMyung-Regular.ttf $B/songmyung/SongMyung-Regular.ttf
curl -sSL -o "fonts/NotoSerifKR[wght].ttf" "$B/notoserifkr/NotoSerifKR%5Bwght%5D.ttf"
curl -sSL -o "fonts/NotoSansKR[wght].ttf" "$B/notosanskr/NotoSansKR%5Bwght%5D.ttf"
