# -*- coding: utf-8 -*-
"""LEGO 追蹤器桌面版：用獨立視窗開啟 GitHub Pages 上的網站。

- 套組資料：每次開啟都讀網站上最新的 sets.js（由 GitHub Actions 每週更新）
- 勾選進度：網頁本身的 Firebase 雲端同步（同步碼存在本程式自己的資料夾，下次開啟自動連線）
"""
import os
import time
import urllib.request

import webview

URL = 'https://daniel4lee.github.io/lego-tracker/'
DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'LegoTracker')

OFFLINE_HTML = '''<html><body style="background:#0a0a0f;color:#e0e0e0;font-family:'Segoe UI',sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center">
<div><h2 style="color:#f5c518">連不上網路</h2>
<p>LEGO 追蹤器需要網路才能載入最新套組與同步勾選。</p>
<p>請確認網路後關閉此視窗重新開啟。</p></div></body></html>'''


def online():
    try:
        urllib.request.urlopen(URL, timeout=8)
        return True
    except Exception:
        return False


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    webview.settings['ALLOW_DOWNLOADS'] = True  # 「匯出」備份需要
    kw = dict(width=1400, height=900, min_size=(400, 500))
    if online():
        # 加時間參數避開快取，確保拿到最新的 index.html / sets.js
        webview.create_window('星際大戰 LEGO 蒐藏追蹤器', URL + '?app=%d' % time.time(), **kw)
    else:
        webview.create_window('星際大戰 LEGO 蒐藏追蹤器', html=OFFLINE_HTML, **kw)
    # private_mode=False + storage_path：保留 localStorage（同步碼、勾選）
    webview.start(private_mode=False, storage_path=DATA_DIR)


if __name__ == '__main__':
    main()
