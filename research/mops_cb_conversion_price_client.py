"""假設#51子事件3（可轉換公司債轉換價格重設）資料源客戶端——公開資訊觀測站
（MOPS）`t108sb08_1_q2`功能（轉換(附認股權)公司債公告彙總表）。

**2026-09-07本輪突破**：前幾輪反覆卡在「找不到搜尋表單」——真正的關卡不是
表單不存在，是這個功能走MOPS舊式**兩段式AJAX**流程（不是Vue SPA路由本身
擋著），必須依序：
1. GET `https://mopsov.twse.com.tw/mops/web/t108sb08_1_q2`（真人查詢UI頁，
   拿到`form1`完整欄位清單與預設值——年度/月份/公司代號等）。
2. POST `https://mopsov.twse.com.tw/mops/web/ajax_t108sb08_1_q2`（比照該頁
   JS `doAction()`邏輯，`step=1`、`firstin=1`），回應內嵌一個
   `<form name='autoForm' action='/mops/web/ajax_t108sb08_1'>`，帶著
   `run`/`step`/`TYPEK`/`co_id_1`/`co_id_2`/`year`/`month`/`day1`/`day2`/
   `coid`/`firstin`欄位（第一段的用途只是登記查詢條件，真正資料在第二段）。
3. 用第2步回應裡的欄位原樣POST到`https://mopsov.twse.com.tw/mops/web/
   ajax_t108sb08_1`，才拿到真正的資料表格。

這一次POST回傳的是**單一(TYPEK,year,month)組合下全部10種轉換公司債相關
公告類型**合併在一頁（每種類型前面有`<center><font...>類型名稱</font>
</center>`分隔，查無資料的類型是`查無資料`固定字串），我們只取其中
「轉換公司債轉換價格變更公告」這一段，其餘9種（停止轉換/停止過戶/開始
轉換/附認股權相關/SLB）本輪不解析，不是本假設子事件3的範圍。

編碼：實測`Content-Type: text/html; charset=utf-8`為真（不像`ajax_t35sc09`
那樣有Big5爭議），用`requests`預設的`r.encoding='utf-8'`即可正確解碼。

**節流**：MOPS非商用API，逐筆查詢間隔`SLEEP_BETWEEN_CALLS`秒，比照
`mops_buyback_client.py`同一個節流精神（`CLAUDE.md`已知地雷章節）。

尚未驗證：跨多年份/兩個市場(sii/otc)的完整回填涵蓋度（本輪僅驗證單一
(TYPEK='sii', year='113')組合），下一輪待辦：小規模回填2015年至今
（比照`#40`買回股份的per-window快取檔案設計），確認訓練期起點前也有資料。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_mops_cb_conversion_price"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STEP1_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t108sb08_1_q2"
STEP2_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t108sb08_1"
REFERER = "https://mopsov.twse.com.tw/mops/web/t108sb08_1_q2"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": REFERER,
    "Origin": "https://mopsov.twse.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
}
SLEEP_BETWEEN_CALLS = 2.0
MAX_RETRIES = 3

SECTION_TITLE = "轉換公司債轉換價格變更公告"

# 內容描述例：「...自113年07月23日起，轉換價格自39.40元調整為38.80元。」
_DESC_RE = re.compile(
    r"自(\d+)年(\d+)月(\d+)日起.{0,10}?轉換價格自([\d.]+)元調整為([\d.]+)元"
)


def _cache_path(market: str, year: str) -> Path:
    return DATA_DIR / f"CB_CONV_PRICE_{market}_{year}.parquet"


def _step1_autoform_fields(session: requests.Session, typek: str, year: str, month: str = "") -> dict:
    """第一段POST，回傳解析出的autoForm欄位字典（下一段POST要用）。"""
    data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "",
        "inpuType": "co_id",
        "co_id_1": "",
        "co_id_2": "",
        "year": year,
        "TYPEK": typek,
        "month": month,
        "b_date": "",
        "e_date": "",
    }
    r = session.post(STEP1_URL, data=data, headers=HEADERS, timeout=20)
    r.encoding = "utf-8"
    text = r.text
    # 注意：伺服器回應的<form name='autoForm'>從不補上</form>結尾標籤
    # （本輪實測發現的MOPS既有quirk，瀏覽器會自動補齊，但requests不會），
    # 不能用</form>當終止符，改抓到下一個</div>為止。
    form_m = re.search(r"<form name='autoForm'.*?</div>", text, re.S)
    if not form_m:
        raise RuntimeError(f"第一段POST未找到autoForm，回應長度={len(text)}")
    form_html = form_m.group(0)
    fields = {}
    for inp in re.findall(r"<input[^>]*>", form_html):
        name_m = re.search(r"name='([^']*)'", inp)
        val_m = re.search(r"value='([^']*)'", inp)
        if name_m:
            fields[name_m.group(1)] = val_m.group(1) if val_m else ""
    return fields


def _parse_conversion_price_section(html: str) -> list[dict]:
    """從第二段回應裡切出「轉換公司債轉換價格變更公告」那一段並解析成列表。"""
    idx = html.find(SECTION_TITLE)
    if idx == -1:
        return []
    section = html[idx:]
    end_idx = section.find("</table>")
    if end_idx == -1:
        return []
    section = section[: end_idx + len("</table>")]
    if "查無資料" in section:
        return []
    rows = re.findall(r"<tr class='(?:even|odd)'>(.*?)</tr>", section, re.S)
    out = []
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) < 6:
            continue
        category, co_id, stock_name, ann_date_roc, seq_no = tds[0], tds[1], tds[2], tds[3], tds[4]
        desc_html = tds[5]
        desc_text_m = re.search(r"<div[^>]*>(.*?)</div>", desc_html, re.S)
        desc_text = desc_text_m.group(1) if desc_text_m else desc_html
        m = _DESC_RE.search(desc_text)
        eff_date, old_price, new_price = None, None, None
        if m:
            roc_y, mo, dd, old_price, new_price = m.groups()
            eff_date = f"{int(roc_y) + 1911:04d}-{int(mo):02d}-{int(dd):02d}"
        ann_parts = ann_date_roc.split("/")
        ann_date = None
        if len(ann_parts) == 3:
            ann_date = f"{int(ann_parts[0]) + 1911:04d}-{int(ann_parts[1]):02d}-{int(ann_parts[2]):02d}"
        out.append(
            {
                "category": category.strip(),
                "co_id": co_id.strip(),
                "stock_name": stock_name.strip(),
                "announcement_date": ann_date,
                "seq_no": seq_no.strip(),
                "effective_date": eff_date,
                "old_price": float(old_price) if old_price else None,
                "new_price": float(new_price) if new_price else None,
                "description": desc_text.strip(),
            }
        )
    return out


def fetch_conversion_price_events(typek: str, year: str, month: str = "", use_cache: bool = True) -> pd.DataFrame:
    """查詢單一(市場別, 民國年, 月份)組合下的轉換公司債轉換價格變更公告。

    typek: 'sii'(上市)/'otc'(上櫃)/'rotc'(興櫃)/'pub'(公開發行)
    year: 民國年字串，例如'113'（2024年）
    month: 留空字串代表全年
    """
    cache_key = f"{typek}_{year}{('_' + month) if month else ''}"
    cache_path = _cache_path(cache_key, "")
    if use_cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    session = requests.Session()
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            autoform_fields = _step1_autoform_fields(session, typek, year, month)
            time.sleep(SLEEP_BETWEEN_CALLS)
            data = {"encodeURIComponent": "1", **autoform_fields}
            r2 = session.post(STEP2_URL, data=data, headers=HEADERS, timeout=30)
            r2.encoding = "utf-8"
            rows = _parse_conversion_price_section(r2.text)
            df = pd.DataFrame(rows)
            if use_cache:
                df.to_parquet(cache_path)
            return df
        except Exception as e:  # noqa: BLE001 - 逐一重試後才放棄
            last_err = e
            time.sleep(SLEEP_BETWEEN_CALLS)
    raise RuntimeError(f"{typek}/{year}/{month} 查詢失敗，重試{MAX_RETRIES}次仍失敗：{last_err}")


if __name__ == "__main__":
    df = fetch_conversion_price_events("sii", "113")
    print(f"上市113年(2024)轉換價格變更公告筆數：{len(df)}")
    if len(df):
        print(df.head(10).to_string())
