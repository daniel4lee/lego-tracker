# -*- coding: utf-8 -*-
"""更新 sets.js：從 Rebrickable 抓新的星戰套組、自動抓美金官方定價（MSRP）、更新匯率。

規則
- 收錄主題：Star Wars(158) 及其子主題（含 UCS）、Technic/Star Wars、Seasonal/Advent/Star Wars、Mindstorms/Star Wars
- 排除：0 零件的組合包、L000 開頭的贈品
- 已在清單裡且已有價格的套組完全不動（手動填的價格會保留）
- 新套組（或近期尚無價格的一般盒組）會自動從 Brickipedia / Bricker 抓美金官方原價（贈品／鋁箔包維持 null）
- 匯率抓不到就沿用舊值
"""
import csv
import datetime
import gzip
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SETS_JS = os.path.join(HERE, 'sets.js')
INDEX = os.path.join(HERE, 'index.html')

SW_ROOT = '158'
EXTRA_THEMES = {'18', '209', '261'}  # Technic / Advent / Mindstorms 底下的 Star Wars
RB = 'https://cdn.rebrickable.com/media/downloads/'
BRICKIPEDIA_API = 'https://brickipedia.fandom.com/api.php'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) lego-tracker-updater/1.1'}

# 已知無官方零售定價的前綴（雜誌附錄鋁箔包、滿額贈 GWP、店內活動包、展場非賣品等）
NON_RETAIL_PREFIXES = (
    '91', '951', '472', 'L0', '40', '500', '501',
    '617', '621', '625', '638', '647', '65', '662', '664', '665',
    '285', '452', '454', '555', 'EG0', 'SWMP', 'TICKET', 'TOYFAIR',
    'TRU', 'MAY', 'YODA', 'TIEFIGHTER', 'SWCOMIC', 'PORG', 'LUKE',
    'XWING', 'VP-', 'LLCA', 'FANEXPO', 'CELEB', 'COMCON', 'SDCC',
)


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_csv_gz(name):
    raw = gzip.decompress(fetch(RB + name))
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))


def read_sets_js():
    text = open(SETS_JS, encoding='utf-8').read()
    m = re.search(r'const SETS = (\[.*?\n\]);', text, re.S)
    rate = float(re.search(r'const USD_TWD = ([\d.]+);', text).group(1))
    return json.loads(m.group(1)), rate


def write_sets_js(sets, rate, today):
    lines = [json.dumps(s, ensure_ascii=False, separators=(',', ':')) for s in sets]
    out = ('// 由 update_sets.py 產生。price 是美金建議售價，可直接手動修改，下次更新會保留。\n'
           'const DATA_UPDATED = "%s";\n'
           'const USD_TWD = %s;\n'
           'const SETS = [\n%s\n];\n') % (today, rate, ',\n'.join(lines))
    with open(SETS_JS, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)


def is_retail_candidate(set_num):
    return not set_num.upper().startswith(NON_RETAIL_PREFIXES)


def parse_brickipedia_price(wikitext):
    if not wikitext:
        return None
    m_block = re.search(r'\|\s*Price\s*=\s*(\{\{Price.*?\}\}|[^\n|]+)', wikitext, re.I | re.S)
    if not m_block:
        return None
    block = m_block.group(1)
    # 若標明為贈品 / 非賣品且無美金售價則略過
    after_block = wikitext[m_block.end():m_block.end() + 80]
    if re.search(r'\bfree\b|promotional|gift with purchase|not for sale', block + ' ' + after_block, re.I):
        if not re.search(r'\|\s*US\s*=\s*\$?\s*\d', block, re.I):
            return None
    m_us = re.search(r'\|\s*US\s*=\s*\$?\s*([\d,]+(?:\.\d+)?)', block, re.I)
    if m_us:
        val = float(m_us.group(1).replace(',', ''))
        if val > 0:
            return int(val) if val.is_integer() else val
    if not block.strip().startswith('{{'):
        mu = re.search(r'(?:US\s*\$|USD\s*|\$)([\d,]+(?:\.\d+)?)', block)
        if mu:
            val = float(mu.group(1).replace(',', ''))
            if val > 0:
                return int(val) if val.is_integer() else val
    return None


def query_brickipedia_revisions(titles):
    if not titles:
        return {}
    results = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        url = BRICKIPEDIA_API + '?' + urllib.parse.urlencode({
            'action': 'query',
            'prop': 'revisions',
            'rvprop': 'content',
            'redirects': '1',
            'format': 'json',
            'titles': '|'.join(batch),
        })
        try:
            data = json.loads(fetch(url, timeout=30).decode('utf-8'))
        except Exception:
            continue
        norm = {n['from']: n['to'] for n in data.get('query', {}).get('normalized', [])}
        redirs = {r['from']: r['to'] for r in data.get('query', {}).get('redirects', [])}
        pages = {}
        for p in data.get('query', {}).get('pages', {}).values():
            if 'revisions' in p:
                pages[p['title']] = p['revisions'][0].get('*', '')
        for t in batch:
            cur = norm.get(t, t)
            seen = set()
            while cur in redirs and cur not in seen:
                seen.add(cur)
                cur = redirs[cur]
            if cur in pages:
                results[t] = pages[cur]
    return results


def fetch_bricker_price(base_num):
    try:
        html = fetch('https://bricker.info/sets/%s/' % base_num, timeout=15).decode('utf-8', errors='ignore')
        m = re.search(r"id=['\"]msrp['\"][^>]*>\s*([\d,]+(?:\.\d+)?)\s*<", html, re.I)
        if m:
            val = float(m.group(1).replace(',', ''))
            if val > 0:
                return int(val) if val.is_integer() else val
    except Exception:
        pass
    return None


def fill_missing_prices(target_sets):
    """對 target_sets 裡 price 為 None 的零售盒組查詢官方美金原價（MSRP）。"""
    candidates = [s for s in target_sets if s.get('price') is None and is_retail_candidate(s['num'])]
    if not candidates:
        return 0

    print('查詢 %d 套盒組的官方美金定價…' % len(candidates))
    found = {}

    # 第一輪：直接用編號與「編號 名稱」批次查 Brickipedia
    for use_name in (False, True):
        rem = [s for s in candidates if s['num'] not in found]
        if not rem:
            break
        t_map = {}
        for s in rem:
            base = s['num'].split('-')[0]
            title = ('%s %s' % (base, s['name'])) if use_name else base
            t_map[title] = s
        revs = query_brickipedia_revisions(list(t_map.keys()))
        for title, wt in revs.items():
            p = parse_brickipedia_price(wt)
            if p is not None:
                found[t_map[title]['num']] = p

    # 第二輪：名稱可能與 Rebrickable 略有不同，用 allpages 前綴搜尋條目名稱
    rem = [s for s in candidates if s['num'] not in found]
    prefix_titles = {}
    for s in rem:
        base = s['num'].split('-')[0]
        try:
            url = BRICKIPEDIA_API + '?' + urllib.parse.urlencode({
                'action': 'query',
                'list': 'allpages',
                'apprefix': base + ' ',
                'aplimit': 3,
                'format': 'json',
            })
            ap = json.loads(fetch(url, timeout=15).decode('utf-8'))
            pages = ap.get('query', {}).get('allpages', [])
            if pages:
                prefix_titles[pages[0]['title']] = s
        except Exception:
            pass

    if prefix_titles:
        revs = query_brickipedia_revisions(list(prefix_titles.keys()))
        for title, wt in revs.items():
            p = parse_brickipedia_price(wt)
            if p is not None:
                found[prefix_titles[title]['num']] = p

    # 第三輪：用 Bricker.info 作為備援
    rem = [s for s in candidates if s['num'] not in found]
    for s in rem:
        base = s['num'].split('-')[0]
        p = fetch_bricker_price(base)
        if p is not None:
            found[s['num']] = p

    for s in candidates:
        if s['num'] in found:
            s['price'] = found[s['num']]

    return len(found)


def main():
    backfill_all = '--backfill' in sys.argv
    today_date = datetime.date.today()
    today = today_date.isoformat()
    sets, old_rate = read_sets_js()
    have = {s['num'] for s in sets}
    print('目前清單：%d 套，匯率 %s' % (len(sets), old_rate))

    print('下載 Rebrickable 資料…')
    themes = {r['id']: r for r in load_csv_gz('themes.csv.gz')}
    rb_sets = load_csv_gz('sets.csv.gz')

    def in_scope(tid):
        if tid in EXTRA_THEMES:
            return True
        while tid:
            if tid == SW_ROOT:
                return True
            tid = themes[tid]['parent_id'] if tid in themes else ''
        return False

    added = []
    for r in rb_sets:
        n = r['set_num']
        if n in have or not in_scope(r['theme_id']):
            continue
        if int(r['num_parts']) == 0 or n.startswith('L0'):
            continue
        added.append({'num': n, 'name': r['name'], 'year': int(r['year']),
                      'parts': int(r['num_parts']),
                      'img': r['img_url'] or 'https://cdn.rebrickable.com/media/sets/%s.jpg' % n,
                      'price': None})

    # 對新抓到的套組 + 近期（或 --backfill 全部）尚無價格的盒組自動查官方美金定價
    if backfill_all:
        to_price = [s for s in sets if s.get('price') is None] + added
    else:
        min_year = today_date.year - 1
        to_price = [s for s in sets if s.get('price') is None and s['year'] >= min_year] + added

    priced_count = fill_missing_prices(to_price)

    rate = old_rate
    try:
        d = json.loads(fetch('https://open.er-api.com/v6/latest/USD', 30).decode('utf-8'))
        rate = round(d['rates']['TWD'], 2)
    except Exception as e:
        print('[警告] 匯率抓取失敗，沿用 %s（%s）' % (old_rate, e))

    sets = sorted(sets + added, key=lambda s: (s['year'], s['num']))
    write_sets_js(sets, rate, today)

    # 更新 index.html 的 ?v=，讓瀏覽器重新抓 sets.js
    html = open(INDEX, encoding='utf-8').read()
    html2 = re.sub(r'sets\.js\?v=[\w-]+', 'sets.js?v=' + today.replace('-', ''), html)
    if html2 != html:
        with open(INDEX, 'w', encoding='utf-8', newline='') as f:
            f.write(html2)

    print()
    print('新增 %d 套（本次自動補齊 %d 套官方定價）：' % (len(added), priced_count))
    for s in sorted(added, key=lambda s: (s['year'], s['num'])):
        p_str = ('$%s' % s['price']) if s.get('price') is not None else '無定價'
        print('  %-12s %d  %5d pcs  %-8s  %s' % (s['num'], s['year'], s['parts'], p_str, s['name']))
    print('匯率：%s → %s' % (old_rate, rate))
    no_price = [s for s in sets if not s.get('price')]
    print('共 %d 套，其中 %d 套無官方定價（多為雜誌鋁箔包／滿額贈，亦可於 sets.js 手動填 price）' % (len(sets), len(no_price)))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('[錯誤] %s' % e)
        sys.exit(1)
