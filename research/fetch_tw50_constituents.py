# -*- coding: utf-8 -*-
"""先.一三二-5b：0050（元大台灣50）官方成分股清單 → data/tw50_constituents.json（模擬 K 揭露欄用）。

只用於 research/paper_11_tdcc_bigholder_tracker.py 的 etf_0050_006208_member 揭露欄，不作任何判定。
006208（富邦台灣50）追蹤同一指數（臺灣 50 指數），成分股相同；本檔只抓元大一家，未另做富邦交叉核對。

來源：元大投信官方商品頁 www.yuantaetfs.com/product/detail/0050/ratio（「基金權重-股票」，伺服器端渲染；
HTML 表只畫前 5 檔，完整 50 檔在頁內 window.__NUXT__ 的 FundWeights.StockWeights）。
robots.txt（2026-10-23 查）：User-agent: * Allow: /。官方未公布次數上限。
節流：與 data/rate_limit_state.json 共用（來源名 yuanta_www，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）；
上次抓取未滿 6 天就略過、不送請求（每週約 1 次）。
解析方式：純文字解析 Nuxt 壓縮 IIFE（參數名→呼叫引數對照），**不執行網站的 JavaScript**。
檢核：剛好 50 檔、代號不重複、股票權重合計 90～101%，任一不符就不覆蓋既有檔案、exit 1。
原始頁存 research/data/raw/yuanta_0050_ratio/（research/data/ 已 gitignore），不進公開 repo。
用法：python research/fetch_tw50_constituents.py [--force] [--from-file 已存的.html]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from fetch_0050_nav import _StrictOffAdapter  # noqa: E402  同站憑證缺 Subject Key Identifier，只關 VERIFY_X509_STRICT

SRC = "yuanta_www"
URL = "https://www.yuantaetfs.com/product/detail/0050/ratio"
RAW = HERE / "data" / "raw" / "yuanta_0050_ratio"
OUT = ROOT / "data" / "tw50_constituents.json"
BLOCK = {402, 403, 428, 429}
MIN_DAYS_BETWEEN = 6
TPE = timezone(timedelta(hours=8))


def _scan_to_close(s: str, i: int, open_ch: str, close_ch: str) -> int:
    """s[i] 是 open_ch，回傳對應 close_ch 的位置；略過字串內容。"""
    depth, q = 0, None
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in pairs:
            stack.append(pairs[c])
            depth += 1
        elif c in ")]}":
            if not stack or stack.pop() != c:
                raise ValueError(f"括號不配對 @ {i}")
            depth -= 1
            if depth == 0:
                if c != close_ch:
                    raise ValueError("括號種類不符")
                return i
        i += 1
    raise ValueError("找不到結尾括號")


def _split_top(s: str) -> list[str]:
    out, cur, q, depth, i = [], [], None, 0, 0
    while i < len(s):
        c = s[i]
        if q:
            cur.append(c)
            if c == "\\":
                cur.append(s[i + 1])
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def _literal(tok: str):
    t = tok.strip()
    if t.startswith('"'):
        return json.loads(re.sub(r"\\x([0-9a-fA-F]{2})", r"\\u00\1", t))
    if t in ("true", "!0"):
        return True
    if t in ("false", "!1"):
        return False
    if t in ("null", "void 0"):
        return None
    if re.fullmatch(r"-?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?", t, re.I):
        return float(t) if re.search(r"[.eE]", t) else int(t)
    return ("__unparsed__", t)


def parse_page(html: str) -> dict:
    i = html.index("window.__NUXT__=(function(")
    p0 = html.index("(function(", i) + len("(function(")
    p1 = html.index(")", p0)
    params = [x.strip() for x in html[p0:p1].split(",")]
    b0 = html.index("{", p1)
    b1 = _scan_to_close(html, b0, "{", "}")
    a0 = b1 + 1
    if html[a0] != "(":
        raise ValueError("函式本體後面不是呼叫引數")
    a1 = _scan_to_close(html, a0, "(", ")")
    args = [_literal(x) for x in _split_top(html[a0 + 1:a1])]
    env = dict(zip(params, args + [None] * (len(params) - len(args))))
    body = html[b0:b1 + 1]

    def val(tok: str):
        tok = tok.strip()
        if tok in env:
            return env[tok]
        v = _literal(tok)
        if isinstance(v, tuple):
            raise ValueError(f"無法解析值 {tok}")
        return v

    k = body.index("StockWeights:[")
    l0 = k + len("StockWeights:")
    l1 = _scan_to_close(body, l0, "[", "]")
    rows = []
    for obj in _split_top(body[l0 + 1:l1]):
        if not (obj.startswith("{") and obj.endswith("}")):
            raise ValueError("StockWeights 元素不是物件")
        fields = {}
        for kv in _split_top(obj[1:-1]):
            key, _, v = kv.partition(":")
            fields[key.strip()] = val(v)
        rows.append({"code": str(fields["code"]), "name": fields.get("name"),
                     "weight_pct": fields.get("weights"), "qty": fields.get("qty")})
    m = re.search(r"交易日期:\s*(\d{4})/(\d{2})/(\d{2})", re.sub(r"<[^>]+>", " ", html[:html.index("window.__NUXT__")]))
    as_of = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
    return {"as_of": as_of, "rows": rows}


def validate(p: dict) -> str | None:
    codes = [r["code"] for r in p["rows"]]
    if len(codes) != 50:
        return f"檔數 {len(codes)} ≠ 50"
    if len(set(codes)) != 50:
        return "代號重複"
    if not all(re.fullmatch(r"\d{4}", c) for c in codes):
        return "代號格式不符"
    w = sum(float(r["weight_pct"] or 0) for r in p["rows"])
    if not 90 <= w <= 101:
        return f"權重合計 {w:.2f}% 不在 90～101%"
    if not p["as_of"]:
        return "找不到交易日期"
    return None


def main(argv: list[str]) -> int:
    force = "--force" in argv
    src_file = argv[argv.index("--from-file") + 1] if "--from-file" in argv else None
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
    now = datetime.now(TPE)
    if old and not force and not src_file:
        last = datetime.fromisoformat(old["fetched_at"])
        if now - last < timedelta(days=MIN_DAYS_BETWEEN):
            print(f"上次抓取 {old['fetched_at']}，未滿 {MIN_DAYS_BETWEEN} 天，略過（不送請求）")
            return 0
    if src_file:
        html = Path(src_file).read_text(encoding="utf-8")
    else:
        RAW.mkdir(parents=True, exist_ok=True)
        _rate_limit_wait_or_raise(SRC)
        sess = requests.Session()
        sess.mount("https://", _StrictOffAdapter())
        # 不帶 Referer、不偽裝（CLAUDE.md 取得方式鐵律）；UA 與 fetch_0050_nav.py 相同
        r = sess.get(URL, timeout=90, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code in BLOCK:
            _rate_limit_record_block(SRC, r.status_code, "0050 ratio")
            print(f"HTTP {r.status_code}，封鎖 2 小時，停止")
            return 1
        if r.status_code != 200:
            print(f"HTTP {r.status_code}，不覆蓋既有檔案")
            return 1
        html = r.text
        (RAW / f"ratio_{now:%Y%m%d}.html").write_text(html, encoding="utf-8")
    try:
        p = parse_page(html)
    except (ValueError, KeyError) as e:
        print(f"解析失敗（{e}），不覆蓋既有檔案")
        return 1
    err = validate(p)
    if err:
        print(f"檢核不過：{err}，不覆蓋既有檔案")
        return 1
    codes = sorted(r["code"] for r in p["rows"])
    hist = list((old or {}).get("history") or [])
    if not hist or hist[-1]["codes"] != codes:
        hist.append({"as_of": p["as_of"], "codes": codes})
    doc = {"as_of": p["as_of"], "fetched_at": now.isoformat(timespec="seconds"),
           "source": "元大投信 0050 商品頁「基金權重-股票」（www.yuantaetfs.com/product/detail/0050/ratio）",
           "note": "0050／006208 皆追蹤臺灣 50 指數；只供模擬 K 揭露欄，不作判定。history 只在成分股變動時新增一筆。",
           "codes": codes,
           "weights": [{"code": r["code"], "name": r["name"], "weight_pct": r["weight_pct"]} for r in p["rows"]],
           "history": hist}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{p['as_of']}：{len(codes)} 檔 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
