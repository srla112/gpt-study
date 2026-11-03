# -*- coding: utf-8 -*-
"""해외반응 키워드 트렌드 (2판)

해외반응 영상 전체에서 '지금 조회수가 몰리는 핵심 키워드'를 찾습니다.

실행할 때마다
  1. 해외반응 채널들의 최근 업로드, 해외반응 검색(최신순), 해외(영어권) 원본 영상을 모으고
  2. 영상별 조회수를 오늘 날짜로 기록한 뒤
  3. 최근 3일 동안 늘어난 조회수로 키워드를 분석해 결과.html 과 결과_키워드.csv 를 만듭니다.

추가 설치 없이 Python 3.9 이상에서 돌아갑니다.
  python haeoe_trend.py              # 수집 + 결과 (기본)
  python haeoe_trend.py --report     # 수집 없이 결과만 다시 만들기
  python haeoe_trend.py --quick      # 시험용: 조금만 수집
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sqlite3
import statistics
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dictionary import CATS, NATIONS, BROAD, FOREIGN_QUERIES  # noqa: E402
from keywords import FOREIGN, REACT2, BADCH, KOREA, secs  # noqa: E402

DB = os.path.join(HERE, 'trend.db')
SEED = os.path.join(HERE, 'seed.json')
CHANNELS = os.path.join(HERE, 'channels.json')
OUT = os.path.join(HERE, '결과.html')
OUT_CSV = os.path.join(HERE, '결과_키워드.csv')
WINDOW = 3                 # 최근 며칠 동안의 증가를 볼지
RECENT_DAYS = 14           # '최근 올라온 영상'으로 보는 기간 (경쟁 정도 계산용)
REFRESH_RECENT_DAYS = 90   # 이 기간 안에 올라온 영상은 매일 정확한 조회수를 다시 가져옴
MIN_TRACK = 3000           # 새로 찾은 한국 해외반응 영상 추적 최소 조회수
SMALL_CHANNEL = 10000      # 작은 채널 기준 (구독자)
OUTLIER_X = 3.0            # 채널 평소 조회수(중앙값)의 몇 배면 '터진 영상'으로 볼지
CLIENT = {"client": {"clientName": "WEB", "clientVersion": "2.20261029.01.00", "hl": "ko", "gl": "KR"}}
CLIENT_EN = {"client": {"clientName": "WEB", "clientVersion": "2.20261029.01.00", "hl": "en", "gl": "US"}}
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
TODAY = dt.date.today()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------------- YouTube ----------------
def api(endpoint, body, ctx=CLIENT):
    data = json.dumps(dict(body, context=ctx)).encode()
    for i in range(4):
        try:
            req = urllib.request.Request(f'https://www.youtube.com/youtubei/v1/{endpoint}?prettyPrint=false', data=data,
                                         headers={'Content-Type': 'application/json', 'User-Agent': UA, 'Accept-Language': 'ko'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            time.sleep(2 ** i)
    return {}


def walk(x, key, out):
    if isinstance(x, dict):
        if key in x:
            out.append(x[key])
        for v in x.values():
            walk(v, key, out)
    elif isinstance(x, list):
        for v in x:
            walk(v, key, out)
    return out


def text(o):
    return "".join(r.get('text', '') for r in (o or {}).get('runs', [])) or (o or {}).get('simpleText', '')


def num(s):
    m = re.search(r'([\d.]+)\s*(천|만|억|K|M|B)?', (s or '').replace(',', ''), re.I)
    if not m:
        return 0
    mul = {'천': 1e3, '만': 1e4, '억': 1e8, 'k': 1e3, 'm': 1e6, 'b': 1e9}.get((m.group(2) or '').lower(), 1)
    return int(float(m.group(1)) * mul)


def age_to_date(age):
    m = re.search(r'(\d+)\s*(초|분|시간|일|주|개월|년|second|minute|hour|day|week|month|year)', age or '', re.I)
    if not m:
        return None
    unit = m.group(2).lower()
    days = {'초': 0, '분': 0, '시간': 0, '일': 1, '주': 7, '개월': 30, '년': 365, 'second': 0, 'minute': 0, 'hour': 0,
            'day': 1, 'week': 7, 'month': 30, 'year': 365}[unit]
    return TODAY - dt.timedelta(days=int(m.group(1)) * days)


def search(query, params, pages=1, ctx=CLIENT):
    out = []
    d = api('search', {'query': query, 'params': params}, ctx)
    for _ in range(pages):
        for v in walk(d, 'videoRenderer', []):
            own = (v.get('ownerText') or {}).get('runs', [{}])[0]
            out.append({'id': v['videoId'], 'title': text(v.get('title')), 'views': num(text(v.get('viewCountText'))),
                        'len': text(v.get('lengthText')), 'age': text(v.get('publishedTimeText')), 'ch': own.get('text', ''),
                        'chid': own.get('navigationEndpoint', {}).get('browseEndpoint', {}).get('browseId', '')})
        tok = walk(d, 'continuationCommand', [])
        if not tok:
            break
        d = api('search', {'continuation': tok[-1]['token']}, ctx)
    return out


def channel_latest(chid):
    """채널 동영상 탭 첫 페이지(최신 30개)와 구독자 수."""
    d = api('browse', {'browseId': chid, 'params': 'EgZ2aWRlb3PyBgQKAjoA'})
    name = d.get('metadata', {}).get('channelMetadataRenderer', {}).get('title') or ''
    hs = json.dumps(d.get('header', {}), ensure_ascii=False)
    sm = re.search(r'구독자 ([\d.,]+\s*[천만]?)명', hs)
    vids = []
    for lv in walk(d, 'lockupViewModel', []):
        m = lv.get('metadata', {}).get('lockupMetadataViewModel', {})
        parts = [p['text']['content'] for r in walk(m, 'metadataRows', []) for row in r for p in row.get('metadataParts', [])]
        badge = [b.get('text') for b in walk(lv, 'thumbnailBadgeViewModel', [])]
        vids.append({'id': lv.get('contentId'), 'title': m.get('title', {}).get('content') or '', 'views': num(next((p for p in parts if p.startswith('조회수')), '')),
                     'age': next((p for p in parts if p.endswith('전')), ''), 'len': next((b for b in badge if b and ':' in b), ''), 'ch': name, 'chid': chid})
    return chid, name, num(sm.group(1)) if sm else None, [v for v in vids if v['id']]


def video_info(vid):
    d = api('next', {'videoId': vid})
    p = walk(d, 'videoPrimaryInfoRenderer', [])
    if not p:
        return vid, None
    vc = walk(p, 'videoViewCountRenderer', [])
    m = re.search(r'([\d,]+)', (vc[0].get('viewCount', {}).get('simpleText') if vc else '') or '')
    date = walk(p, 'dateText', [])
    md = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', date[0].get('simpleText', '') if date else '')
    return vid, {'views': int(m.group(1).replace(',', '')) if m else None, 'title': text(p[0].get('title')),
                 'date': f'{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}' if md else None}


# ---------------- 판정 ----------------
HANGUL = re.compile(r'[가-힣]{3}')
ASCII_TITLE = re.compile(r'^[\x00-\x7F\u2000-\u206F\u2600-\u27BF\U0001F000-\U0001FAFF]+$')


def is_kr_reaction(v):
    t = v.get('title') or ''
    return secs(v.get('len')) > 180 and HANGUL.search(t) and FOREIGN.search(t) and REACT2.search(t) and KOREA.search(t) \
        and not BADCH.search(v.get('ch') or '') and not re.search(r'직캠|fancam|^\s*\d{6}\s|감동\s?사연|해외감동|사연\]', t, re.I)


KOREA_EN = re.compile(r'korea|seoul|busan|jeju|hanwoo|kimchi|k-?pop|bts|blackpink|soju|bibimbap|bulgogi|tteokbokki|kimbap|incheon|hongdae|gangnam|myeongdong', re.I)


def is_foreign_original(v):
    t = v.get('title') or ''
    return secs(v.get('len')) > 180 and not re.search(r'[가-힣]', t) and KOREA_EN.search(t) and not BADCH.search(v.get('ch') or '') \
        and not re.search(r'\bLIVE\b|\[LIVE\]|Qualification|Court \d|Day \d+ \||full match|highlights|news|arrival|airport.*BTS|BTS.*airport', t, re.I) \
        and not re.search(r'스타뉴스|디스패치|Dispatch|RNX|BWF|뉴스|News|TV조선|연합|YTN|Arirang|KBS|MBC|SBS', v.get('ch') or '', re.I)


# ---------------- 저장소 ----------------
def db():
    con = sqlite3.connect(DB)
    con.executescript('''
      create table if not exists video(id text primary key, title text, ch text, chid text, date text, len text, added text, kind text default 'kr');
      create table if not exists snap(id text, day text, views integer, primary key(id, day));
      create table if not exists channel(chid text primary key, name text, subs integer, median integer, updated text);
    ''')
    cols = [r[1] for r in con.execute('pragma table_info(video)')]
    if 'kind' not in cols:                     # 1판 기록에서 이어 쓰기
        con.execute("alter table video add column kind text default 'kr'")
    if 'topic' in cols:
        pass
    return con


def norm_date(s):
    m = re.search(r'(\d{4})[.\-]\s*(\d{1,2})[.\-]\s*(\d{1,2})', s or '')
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''


def load_seed(con):
    if con.execute('select count(*) from video').fetchone()[0] == 0 and os.path.exists(SEED):
        seed = json.load(open(SEED, encoding='utf-8'))
        con.executemany('insert or ignore into video(id,title,ch,chid,date,len,added,kind) values(?,?,?,?,?,?,?,?)',
                        [(v['id'], v['title'], v['ch'], v['chid'], norm_date(v['date']), v['len'], '2026-11-01', 'kr') for v in seed])
        con.executemany('insert or ignore into snap values(?,?,?)', [(v['id'], '2026-11-01', v['views']) for v in seed])
        log('처음 실행: 기존 해외반응 영상', len(seed), '개를 넣었습니다 (기준일 2026-11-01)')
    if os.path.exists(CHANNELS):
        con.executemany('insert or ignore into channel(chid,name) values(?,?)', [(c['chid'], c['name']) for c in json.load(open(CHANNELS, encoding='utf-8'))])
    for vid, d in con.execute("select id, date from video where date like '%.%'").fetchall():   # 1판 날짜 형식 바꾸기
        con.execute('update video set date=? where id=?', (norm_date(d), vid))
    con.commit()


def add_videos(con, vids, kind):
    today = TODAY.isoformat()
    known = {r[0] for r in con.execute('select id from video')}
    new = 0
    for v in vids:
        d = age_to_date(v.get('age'))
        if v['id'] not in known:
            con.execute('insert or ignore into video(id,title,ch,chid,date,len,added,kind) values(?,?,?,?,?,?,?,?)',
                        (v['id'], v['title'], v.get('ch', ''), v.get('chid', ''), d.isoformat() if d else '', v.get('len', ''), today, kind))
            known.add(v['id'])
            new += 1
        if v.get('views'):
            con.execute('insert or ignore into snap values(?,?,?)', (v['id'], today, v['views']))   # 대략값; 정확값이 오면 덮어씀
    con.commit()
    return new


# ---------------- 1. 수집 ----------------
def collect(con, quick=False):
    # 1-1 해외반응 채널 최근 업로드
    chids = [r[0] for r in con.execute('select chid from channel')]
    if quick:
        chids = chids[:60]
    log(f'1/4 해외반응 채널 {len(chids)}개의 최근 업로드 확인')
    got = []
    with ThreadPoolExecutor(8) as ex:
        for chid, name, subs, vids in ex.map(channel_latest, chids):
            views = [v['views'] for v in vids if v['views']]
            med = int(statistics.median(views)) if views else None
            con.execute('update channel set name=coalesce(?,name), subs=coalesce(?,subs), median=coalesce(?,median), updated=? where chid=?',
                        (name or None, subs, med, TODAY.isoformat(), chid))
            got += [v for v in vids if v['views'] >= MIN_TRACK and is_kr_reaction(v)]
    log('    새로 넣은 영상', add_videos(con, got, 'kr'), '개')
    # 1-2 해외반응 검색 (최신순)
    jobs = [(q, sp, 2) for q in BROAD for sp in ('CAISBBABGAM=', 'CAISBBABGAI=')]
    for cat in CATS.values():
        for name, (rx, en) in cat.items():
            jobs.append((f'해외반응 {name.split("·")[0]}', 'CAISBBABGAM=', 1))
    if quick:
        jobs = jobs[:30]
    log(f'2/4 해외반응 검색 {len(jobs)}번 (최신순)')
    got = []
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(lambda a: search(*a), jobs):
            got += [v for v in res if v['views'] >= MIN_TRACK and is_kr_reaction(v)]
    for v in got:   # 처음 보는 채널도 다음부터 채널 확인 대상에 넣음
        if v['chid']:
            con.execute('insert or ignore into channel(chid,name) values(?,?)', (v['chid'], v['ch']))
    log('    새로 넣은 영상', add_videos(con, got, 'kr'), '개')
    # 1-3 해외 원본 (영어권, 이번 주 업로드)
    qs = FOREIGN_QUERIES + [en for cat in CATS.values() for (rx, en) in cat.values()]
    qs = list(dict.fromkeys(qs))[: 15 if quick else None]
    log(f'3/4 해외 원본 검색 {len(qs)}번 (이번 주 업로드)')
    got = []
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(lambda q: search(q, 'EgQIAxAB', 2, CLIENT_EN), qs):
            got += [v for v in res if v['views'] >= 5000 and is_foreign_original(v)]
    log('    새로 넣은 원본', add_videos(con, got, 'org'), '개')


# ---------------- 2. 정확한 조회수 ----------------
def refresh(con, quick=False):
    cut = (TODAY - dt.timedelta(days=REFRESH_RECENT_DAYS)).isoformat()
    ids = [r[0] for r in con.execute("select id from video where date='' or date is null or date>=?", (cut,))]
    # 오래된 영상은 이틀에 한 번 (요일 번갈아)
    old = [r[0] for r in con.execute("select id from video where date<>'' and date<?", (cut,))]
    old = [i for i in old if hash(i) % 2 == TODAY.toordinal() % 2]
    ids = list(dict.fromkeys(ids + old))
    if quick:
        ids = ids[:300]
    log(f'4/4 정확한 조회수 가져오기 {len(ids)}개 (몇 분~수십 분)')
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for vid, info in ex.map(video_info, ids):
            n += 1
            if info and info['views'] is not None:
                con.execute('insert or replace into snap values(?,?,?)', (vid, TODAY.isoformat(), info['views']))
                if info['date']:
                    con.execute('update video set date=? where id=?', (info['date'], vid))
            if n % 1000 == 0:
                con.commit()
                log('   ', n, '/', len(ids))
    con.commit()


# ---------------- 3. 분석 ----------------
STOP = set('''반응 외국인 외국인들 해외 해외반응 한국 한국인 한국의 한국에 한국을 한국은 한국이 대한민국 우리나라 경악 충격 놀란 놀라 이유 처음 난생처음
 인생 결국 진짜 정말 완전 역대급 레전드 대박 실제 최근 지금 현재 미친 영상 모음 몰아보기 그녀 그들 사람 사람들 전세계 세계 세계가 전
 반했다 감탄 극찬 리액션 외신 현지 네티즌 해외네티즌 처음본 처음먹어본 먹어본 가본 타본 해본 보고 보더니 했더니 하자 하는 했다 한다 했던
 무슨 어떻게 이게 이건 저게 여기 거기 그냥 바로 갑자기 다시 너무 진심 소름 ㄷㄷ ㅋㅋ ㅋㅋㅋ 일본 미국 영국 중국 프랑스 독일 일본인 미국인 영국인 중국인
 가족 부모님 아내 남편 친구 여친 남친 장모님 국제커플 커플 부부 브이로그 vlog 먹방 eng sub ENG SUB shorts 해외감동 감동 사연'''.split())
JOSA = re.compile(r'(은|는|이|가|을|를|의|에|에서|에게|께|로|으로|와|과|도|만|까지|부터|이랑|랑|한테|보다|처럼|이라|라고|이다|입니다|했다|하는)$')
QUOTE = re.compile(r'[《「『\[‘\'"“]([^《》「」『』\[\]‘’\'"“”]{2,20})[》」』\]’\'"”]')
HASHTAG = re.compile(r'#([0-9A-Za-z가-힣_]{2,20})')
VERBISH = re.compile(r'(난|던|된|한|인|받|운|는|를|했|하|해|되|돼|져|진|친|쳤|운|줬|봤|갔|왔|있|없|싶|같|겠|요|죠|네|다|니|까|게|며|면|서|고)$')


def series(con, ids):
    """영상별 날짜→조회수."""
    s = defaultdict(dict)
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        for vid, day, views in con.execute(f'select id, day, views from snap where id in ({",".join("?" * len(chunk))})', chunk):
            s[vid][day] = views
    return s


def gain_between(sv, start, end, upload):
    """start 이전 마지막 기록 → end 이전 마지막 기록 사이 증가. 기간 중 올라온 영상은 0에서 시작."""
    days = sorted(sv)
    a = [d for d in days if d <= start]
    b = [d for d in days if d <= end]
    if not b:
        return None
    if a:
        return max(sv[b[-1]] - sv[a[-1]], 0)
    if upload and upload > start:
        return sv[b[-1]]
    return None


def analyze(con):
    days = [r[0] for r in con.execute('select distinct day from snap order by day')]
    cur = days[-1]
    target = (dt.date.fromisoformat(cur) - dt.timedelta(days=WINDOW)).isoformat()
    base = max([d for d in days if d <= target], default=days[0])
    prev_target = (dt.date.fromisoformat(base) - dt.timedelta(days=WINDOW)).isoformat()
    prev = max([d for d in days if d <= prev_target], default=None)
    span = (dt.date.fromisoformat(cur) - dt.date.fromisoformat(base)).days
    chan = {r[0]: {'name': r[1], 'subs': r[2], 'median': r[3]} for r in con.execute('select chid, name, subs, median from channel')}
    rows = con.execute('select id, title, ch, chid, date, kind from video').fetchall()
    S = series(con, [r[0] for r in rows])
    V = []
    SAGA = re.compile(r'감동\s?사연|해외감동|사연\]')
    for vid, title, ch, chid, date, kind in rows:
        if SAGA.search(title or ''):
            continue
        sv = S.get(vid)
        if not sv:
            continue
        g = gain_between(sv, base, cur, date)
        if g is None:
            continue
        gp = gain_between(sv, prev, base, date) if prev else None
        last = sv[max(sv)]
        c = chan.get(chid, {})
        upd = dt.date.fromisoformat(date) if date else None
        age = (TODAY - upd).days if upd else None
        V.append({'id': vid, 't': title, 'ch': ch or c.get('name') or '', 'chid': chid, 'date': date, 'kind': kind, 'views': last, 'g': g, 'gp': gp,
                  'new': bool(date and date > base), 'age': age, 'subs': c.get('subs'), 'med': c.get('median'), 'sv': sv})
    KR = [v for v in V if v['kind'] == 'kr']
    ORG = [v for v in V if v['kind'] == 'org']
    # 일별 증가 (그래프용)
    day_list = days[-15:]

    def daily(vs):
        out = []
        for a, b in zip(day_list, day_list[1:]):
            tot = 0
            for v in vs:
                sv = v['sv']
                if a in sv and b in sv:
                    tot += max(sv[b] - sv[a], 0)
                elif b in sv and v['date'] and a < v['date'] <= b:
                    tot += sv[b]
            out.append(tot)
        return out

    def stats(name, cat, vs, en, rx=None):
        vs = [v for v in vs if v['g'] > 0 or v['new']]
        if not vs:
            return None
        g = sum(v['g'] for v in vs)
        gp = sum(v['gp'] or 0 for v in vs) if prev else None
        recent = [v for v in vs if v['age'] is not None and v['age'] <= RECENT_DAYS]
        nch = len({v['chid'] for v in recent})
        small = [v for v in vs if v['subs'] and v['subs'] < SMALL_CHANNEL and v['views'] >= 50000]
        outl = [v for v in vs if v['med'] and v['med'] > 0 and v['views'] >= 50000 and v['views'] / v['med'] >= OUTLIER_X]
        nat = Counter()
        for v in vs:
            for n, nrx in NATIONS.items():
                if re.search(nrx, v['t']):
                    nat[n] += v['g']
        new_share = sum(v['g'] for v in vs if v['age'] is not None and v['age'] <= 7) / g if g else 0
        rise = ((g - gp) / gp * 100) if gp else None
        if len(recent) >= 15:
            stage = '과열'
        elif new_share >= 0.6 and len(recent) <= 6:
            stage = '새싹'
        elif rise is not None and rise >= 30:
            stage = '상승'
        elif rise is not None and rise <= -30:
            stage = '하락'
        else:
            stage = '유지'
        opp = g / (len(recent) + 2)
        top = sorted(vs, key=lambda v: -v['g'])
        return {'k': name, 'c': cat, 'g': g, 'gp': gp, 'rise': rise, 'n': len(vs), 'nr': len(recent), 'nch': nch, 'opp': opp,
                'small': len(small), 'out': len(outl), 'stage': stage, 'en': en,
                'nat': [[n, x] for n, x in nat.most_common(4) if x > 0], 'daily': daily(vs),
                'v': [vid_row(v) for v in top[:40]]}

    def vid_row(v):
        return [v['id'], v['t'], v['ch'], v['chid'], v['date'], v['views'], v['g'], 1 if v['new'] else 0, v['subs'] or 0,
                round(v['views'] / v['med'], 1) if v['med'] else 0]

    kws = []
    for cat, terms in CATS.items():
        for name, (rx, en) in terms.items():
            r = re.compile(rx, re.I)
            vs = [v for v in KR if r.search(v['t'])]
            st = stats(name, cat, vs, en)
            if st:
                kws.append(st)
    # 자동 발견: 사전에 없는 단어 중, 평소 제목에서는 드문데 최근 조회수가 늘어난 영상에 몰린 단어
    quoted = set()

    def tokens(t):
        toks = set()
        for m in QUOTE.findall(t):
            m = m.strip()
            if 2 <= len(m) <= 14 and not re.fullmatch(r'[\d\s.,!?~%]+', m) and ' ' in m or (2 <= len(m) <= 14 and re.search(r'[가-힣]{2}', m) and len(m) >= 4):
                toks.add(m)
                quoted.add(m)
        toks.update(HASHTAG.findall(t))
        for w in re.findall(r'[가-힣A-Za-z0-9]{2,12}', t):
            w2 = JOSA.sub('', w)
            if len(w2) >= 2 and not VERBISH.search(w2) and not re.fullmatch(r'\d+[가-힣A-Za-z]{0,2}', w2):
                toks.add(w2)
        return {x for x in toks if x not in STOP and x.lower() not in STOP}
    allc = Counter()
    for v in KR:
        allc.update(tokens(v['t']))
    pool = [v for v in KR if v['g'] > 0]
    cand = defaultdict(list)
    for v in pool:
        for t in tokens(v['t']):
            cand[t].append(v)
    N_all = max(len(KR), 1)
    G_all = max(sum(v['g'] for v in pool), 1)
    auto = []
    for t, vs in cand.items():
        hot = [v for v in vs if v['g'] >= 3000]
        if len({v['chid'] for v in hot}) < 3:
            continue
        if t not in quoted and allc[t] > 0.003 * N_all:   # 원래 제목에 흔한 말
            continue
        # 이 단어가 가져간 증가 조회수 몫 ÷ 이 단어가 전체 제목에서 차지하는 몫
        lift = (sum(v['g'] for v in vs) / G_all) / (allc[t] / N_all)
        if lift < (2 if t in quoted else 4):
            continue
        if any(re.search(rx, t, re.I) for terms in CATS.values() for rx, _ in terms.values()):
            continue
        st = stats(t, '새로 뜨는 키워드', vs, t)
        if st and st['g'] > 0:
            st['lift'] = round(lift, 1)
            auto.append(st)
    auto.sort(key=lambda s: -s['g'])
    # 같은 영상 묶음을 가리키는 단어는 하나만
    seen, auto2 = [], []
    for s_ in auto:
        ids = {x[0] for x in s_['v'][:10]}
        if any(len(ids & o) >= 0.6 * len(ids) for o in seen):
            continue
        seen.append(ids)
        auto2.append(s_)
        if len(auto2) >= 60:
            break
    # 터진 영상(아웃라이어)
    outliers = sorted([v for v in KR if v['med'] and v['views'] >= 50000 and v['views'] / v['med'] >= OUTLIER_X and v['g'] > 0],
                      key=lambda v: -(v['g']))[:150]
    # 해외 원본: 하루 평균 조회수
    ORG = [v for v in ORG if not re.search(r'\bLIVE\b|\[LIVE\]|Qualification|Court \d|Day \d+ \||full match|highlights|\bnews\b|arrival|airport', v['t'], re.I)
           and not re.search(r'스타뉴스|디스패치|Dispatch|RNX|BWF|뉴스|News|TV조선|연합|YTN|Arirang|KBS|MBC|SBS', v['ch'] or '', re.I)
           and re.search(r'korea|seoul|busan|jeju|hanwoo|kimchi|k-?pop|bts|blackpink|soju|bibimbap|bulgogi|tteokbokki|kimbap|incheon|hongdae|gangnam|myeongdong', v['t'], re.I)
           and not re.search(r'north korea', v['t'], re.I)]
    for v in ORG:
        v['vel'] = v['views'] / max(1, (v['age'] if v['age'] is not None else 7))
    orgs = sorted([v for v in ORG if v['age'] is not None and v['age'] <= 14], key=lambda v: -v['vel'])[:150]
    org_rows = []
    for v in orgs:
        kw = next((name for terms in CATS.values() for name, (rx, en) in terms.items()
                   if any(len(w) >= 5 and re.search(r'\b' + re.escape(w) + r'\b', v['t'], re.I) for w in en.split() if w.lower() not in GENERIC_EN)), '')
        org_rows.append([v['id'], v['t'], v['ch'], v['date'], v['views'], int(v['vel']), kw])
    return {'cur': cur, 'base': base, 'prev': prev, 'span': span, 'days': day_list, 'kw': kws, 'auto': auto2,
            'out': [vid_row(v) for v in outliers], 'org': org_rows, 'nkr': len(KR), 'norg': len(ORG)}


GENERIC_EN = set('korean korea first time reaction travel vlog trying try in the of and vs fans food live market street store family school mountain river train island national team cold noodles soup'.split())


def write(res):
    data = json.dumps(res, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    open(OUT, 'w', encoding='utf-8').write(tpl.replace('__DATA__', data))
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['분류', '키워드', f'최근{res["span"]}일 늘어난 조회수', '이전 같은 기간', '상승률(%)', '단계', '기회 점수', '늘어난 영상 수',
                    f'최근{RECENT_DAYS}일 올라온 영상', '채널 수', '작은 채널 성공', '터진 영상', '잘 되는 국적', '영어 원본 검색어', '대표 영상', '대표 영상 링크'])
        for s in sorted(res['kw'] + res['auto'], key=lambda s: -s['g']):
            top = s['v'][0] if s['v'] else None
            w.writerow([s['c'], s['k'], s['g'], s['gp'] if s['gp'] is not None else '', round(s['rise']) if s['rise'] is not None else '',
                        s['stage'], int(s['opp']), s['n'], s['nr'], s['nch'], s['small'], s['out'], ' '.join(n for n, _ in s['nat']), s['en'],
                        top[1] if top else '', f'https://www.youtube.com/watch?v={top[0]}' if top else ''])
    log('결과 저장:', OUT)
    log('엑셀용 저장:', OUT_CSV)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true', help='수집 없이 결과만 다시 만들기')
    ap.add_argument('--quick', action='store_true', help='시험용: 조금만 수집')
    ap.add_argument('--no-open', action='store_true', help='결과를 브라우저로 열지 않기')
    a = ap.parse_args()
    con = db()
    load_seed(con)
    if not a.report:
        collect(con, a.quick)
        refresh(con, a.quick)
    res = analyze(con)
    log(f'비교 기간 {res["base"]} → {res["cur"]} ({res["span"]}일), 해외반응 영상 {res["nkr"]}개, 해외 원본 {res["norg"]}개')
    write(res)
    if not a.no_open:
        webbrowser.open('file:///' + OUT.replace('\\', '/'))


if __name__ == '__main__':
    main()
