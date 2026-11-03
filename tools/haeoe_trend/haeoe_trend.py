# -*- coding: utf-8 -*-
"""해외반응 키워드 트렌드: 36개 주제 중 최근 3일 동안 조회수가 많이 늘어난 주제를 보여 줍니다.

실행할 때마다
  1. 주제별로 최근 올라온 해외반응 영상을 찾아 추적 목록에 넣고
  2. 추적 중인 영상의 현재 조회수를 오늘 날짜로 기록한 뒤
  3. 3일 전 기록과 비교해 늘어난 조회수를 주제별로 더해 결과.html 을 만듭니다.

추가 설치 없이 Python 3.9 이상에서 돌아갑니다.
  python haeoe_trend.py            # 수집 + 결과 만들기 (기본)
  python haeoe_trend.py --report   # 수집 없이 결과만 다시 만들기
  python haeoe_trend.py --limit 200  # 시험용: 조회수는 200개만 갱신
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from keywords import T, assign, ok3  # noqa: E402

DB = os.path.join(HERE, 'trend.db')
SEED = os.path.join(HERE, 'seed.json')
OUT = os.path.join(HERE, '결과.html')
WINDOW_DAYS = 3
MIN_VIEWS_TO_TRACK = 10000      # 새로 찾은 영상 중 이 조회수 이상만 추적
DROP_AFTER_DAYS = 365           # 이만큼 지난 영상 중 3일 증가가 거의 없는 영상은 갱신을 건너뜀 (속도용)
CLIENT = {"client": {"clientName": "WEB", "clientVersion": "2.20261029.01.00", "hl": "ko", "gl": "KR"}}
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---------- YouTube ----------
def api(endpoint, body):
    data = json.dumps(dict(body, context=CLIENT)).encode()
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


def search(query, params, pages=1):
    out = []
    d = api('search', {'query': query, 'params': params})
    for _ in range(pages):
        for v in walk(d, 'videoRenderer', []):
            m = re.search(r'(\d+)', text(v.get('viewCountText')).replace(',', ''))
            own = (v.get('ownerText') or {}).get('runs', [{}])[0]
            out.append({'id': v['videoId'], 'title': text(v.get('title')), 'views': int(m.group(1)) if m else 0,
                        'len': text(v.get('lengthText')), 'ch': own.get('text', ''), 'age': text(v.get('publishedTimeText')),
                        'chid': own.get('navigationEndpoint', {}).get('browseEndpoint', {}).get('browseId', '')})
        tok = walk(d, 'continuationCommand', [])
        if not tok:
            break
        d = api('search', {'continuation': tok[-1]['token']})
    return out


def video_info(vid):
    d = api('next', {'videoId': vid})
    p = walk(d, 'videoPrimaryInfoRenderer', [])
    if not p:
        return vid, None
    vc = walk(p, 'videoViewCountRenderer', [])
    m = re.search(r'([\d,]+)', (vc[0].get('viewCount', {}).get('simpleText') if vc else '') or '')
    date = walk(p, 'dateText', [])
    return vid, {'views': int(m.group(1).replace(',', '')) if m else None,
                 'title': text(p[0].get('title')), 'date': date[0].get('simpleText') if date else ''}


# ---------- 저장소 ----------
def db():
    con = sqlite3.connect(DB)
    con.executescript('''
      create table if not exists video(id text primary key, topic text, title text, ch text, chid text, date text, len text, added text);
      create table if not exists snap(id text, day text, views integer, primary key(id, day));
    ''')
    return con


def load_seed(con):
    if con.execute('select count(*) from video').fetchone()[0] or not os.path.exists(SEED):
        return
    seed = json.load(open(SEED, encoding='utf-8'))
    con.executemany('insert or ignore into video values(?,?,?,?,?,?,?,?)',
                    [(v['id'], v['topic'], v['title'], v['ch'], v['chid'], v['date'], v['len'], '2026-11-01') for v in seed])
    con.executemany('insert or ignore into snap values(?,?,?)', [(v['id'], '2026-11-01', v['views']) for v in seed])
    con.commit()
    log('처음 실행: 기존 영상', len(seed), '개를 추적 목록에 넣었습니다 (기준일 2026-11-01)')


def parse_date(s):
    m = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', s or '')
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def age_to_date(age, today):
    m = re.search(r'(\d+)\s*(초|분|시간|일|주|개월|년)', age or '')
    if not m:
        return ''
    n = int(m.group(1)) * {'초': 0, '분': 0, '시간': 0, '일': 1, '주': 7, '개월': 30, '년': 365}[m.group(2)]
    d = today - dt.timedelta(days=n)
    return f'{d.year}. {d.month}. {d.day}.'


# ---------- 1. 새 영상 찾기 ----------
def discover(con):
    PRE = ['해외반응 {}', '외국인 {} 반응', '{} 외국인']
    jobs = [(p.format(w), sp) for words, _ in T.values() for w in words for p in PRE
            for sp in ('CAISBBABGAM=', 'CAISBBABGAI=')]   # 최신 업로드순: 4~20분 / 20분 이상
    log('1/3 새 영상 찾기: 검색', len(jobs), '번')
    found = {}
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(lambda a: search(a[0], a[1], 2), jobs):
            for v in res:
                found[v['id']] = v
    known = {r[0] for r in con.execute('select id from video')}
    today = dt.date.today().isoformat()
    new = [v for v in found.values() if v['id'] not in known and v['views'] >= MIN_VIEWS_TO_TRACK and ok3(v)]
    con.executemany('insert or ignore into video values(?,?,?,?,?,?,?,?)',
                    [(v['id'], assign(v['title']), v['title'], v['ch'], v['chid'], age_to_date(v.get('age'), dt.date.today()), v['len'], today) for v in new])
    # 검색 결과에 나온 조회수를 오늘 기록으로 바로 저장 (따로 다시 조회하지 않아도 됨)
    con.executemany('insert or ignore into snap values(?,?,?)', [(v['id'], today, v['views']) for v in new])
    con.commit()
    log('   새로 추적할 영상', len(new), '개')


# ---------- 2. 조회수 기록 ----------
def refresh(con, limit=None):
    today = dt.date.today()
    rows = con.execute('select id, date from video').fetchall()
    done = {r[0] for r in con.execute('select id from snap where day=?', (today.isoformat(),))}
    ids = []
    for vid, date in rows:
        if vid in done:
            continue
        d = parse_date(date)
        if d and (today - d).days > DROP_AFTER_DAYS:
            last = con.execute('select views from snap where id=? order by day desc limit 2', (vid,)).fetchall()
            if len(last) == 2 and last[0][0] - last[1][0] < 300:
                continue   # 오래되고 거의 안 크는 영상은 하루 걸러 갱신
        ids.append(vid)
    if limit:
        ids = ids[:limit]
    log('2/3 조회수 기록:', len(ids), '개 (몇 분~수십 분 걸립니다)')
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for vid, info in ex.map(video_info, ids):
            n += 1
            if info and info['views'] is not None:
                con.execute('insert or replace into snap values(?,?,?)', (vid, today.isoformat(), info['views']))
                if info['date']:
                    con.execute('update video set date=?, title=? where id=?', (info['date'], info['title'] or None, vid))
            if n % 500 == 0:
                con.commit()
                log('   ', n, '/', len(ids))
    con.commit()


# ---------- 3. 결과 만들기 ----------
def growth(con):
    today = dt.date.today()
    target = today - dt.timedelta(days=WINDOW_DAYS)
    days = [r[0] for r in con.execute('select distinct day from snap order by day')]
    past = [d for d in days if d <= target.isoformat()]
    base_day = past[-1] if past else (days[0] if days else today.isoformat())
    cur_day = days[-1] if days else today.isoformat()
    span = (dt.date.fromisoformat(cur_day) - dt.date.fromisoformat(base_day)).days
    vids = []
    for vid, topic, title, ch, chid, date in con.execute('select id, topic, title, ch, chid, date from video'):
        cur = con.execute('select views from snap where id=? and day<=? order by day desc limit 1', (vid, cur_day)).fetchone()
        if not cur:
            continue
        base = con.execute('select views from snap where id=? and day<=? order by day desc limit 1', (vid, base_day)).fetchone()
        up = parse_date(date)
        is_new = bool(up and up > dt.date.fromisoformat(base_day))
        if base:
            gain = cur[0] - base[0]
        elif is_new:
            gain = cur[0]          # 기준일 뒤에 올라온 영상은 조회수 전체가 증가분
        else:
            continue               # 비교할 기록이 아직 없음
        vids.append({'id': vid, 'topic': topic, 'title': title, 'ch': ch, 'chid': chid, 'date': date,
                     'views': cur[0], 'gain': max(gain, 0), 'new': is_new})
    return vids, base_day, cur_day, span


def report(con):
    vids, base_day, cur_day, span = growth(con)
    topics = []
    for tp in T:
        vs = sorted([v for v in vids if v['topic'] == tp], key=lambda v: -v['gain'])
        topics.append({'t': tp, 'gain': sum(v['gain'] for v in vs), 'n': sum(1 for v in vs if v['gain'] > 0),
                       'new': sum(1 for v in vs if v['new']), 'v': [[v['title'], v['ch'], v['chid'], v['date'], v['views'], v['gain'], v['id'], v['new']]
                                                                   for v in vs if v['gain'] > 0][:200]})
    topics.sort(key=lambda t: -t['gain'])
    data = json.dumps({'t': topics, 'base': base_day, 'cur': cur_day, 'span': span}, ensure_ascii=False).replace('</', '<\\/')
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    open(OUT, 'w', encoding='utf-8').write(tpl.replace('__DATA__', data))
    log('3/3 결과 저장:', OUT, f'(비교 기간 {base_day} → {cur_day}, {span}일)')
    return OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', action='store_true', help='수집 없이 결과만 다시 만들기')
    ap.add_argument('--limit', type=int, help='시험용: 조회수 갱신 개수 제한')
    ap.add_argument('--no-open', action='store_true', help='결과를 브라우저로 열지 않기')
    a = ap.parse_args()
    con = db()
    load_seed(con)
    if not a.report:
        discover(con)
        refresh(con, a.limit)
    out = report(con)
    if not a.no_open:
        webbrowser.open('file:///' + out.replace('\\', '/'))


if __name__ == '__main__':
    main()
