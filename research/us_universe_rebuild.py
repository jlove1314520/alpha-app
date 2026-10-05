# -*- coding: utf-8 -*-
"""先.十八-一：美股母體重建（只建資料，不計任何報酬）。

總司令 2026-10-05【先.十八】一：
  1. 掃 SEC full-index 2010Q1～2026Q3 全量；Form 25／25-NSE **必須解析證券類別**，
     只有普通股（Common Stock／Ordinary Shares／Class A/B）下市才標 delisted。
  2. 另加「最後一次 10-K／10-Q 申報日」欄，超過 15 個月未申報者標 stopped_filing。
  3. 產出 research/data/us_universe_pit.json 新版（舊版另存 .v1.bak 不覆蓋刪除）。

為什麼走 full-index 而不是逐 CIK 打 submissions：form.idx 每季一個檔，裡面有該季
**所有申報人的所有申報**，一次掃描同時得到 (a) Form 25／25-NSE 清單 (b) 每家最後一次
10-K／10-Q 的日期 (c) 完整歷史申報人母體（含早已下市、現在沒有 ticker 的公司）——
67 次請求取代約兩萬次。**這正是舊版 us_universe_pit.py 做不到的地方**：
舊版從 company_tickers.json（只含「現在還有 ticker」者）出發，結構上不可能看到
2012 年倒掉的公司，所以它的 survivorship-free 是假的。

SEC 流量禮儀（官方 10 req/秒）：固定 sleep 0.2 秒（約 5 req/秒），全部回應落地快取
（research/data/raw/sec_idx/、sec_form25/，整個 research/data 已 gitignore），可中斷續跑。

用法：
  python research/us_universe_rebuild.py --index      # 步驟1：掃 form.idx
  python research/us_universe_rebuild.py --form25     # 步驟2：抓 Form 25 本文解析證券類別
  python research/us_universe_rebuild.py --build      # 步驟3：合成新版名冊＋報告
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from sec_rate_limiter import acquire_slot as _shared_acquire_slot

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
IDX = RAW / "sec_idx"
F25 = RAW / "sec_form25"
for d in (IDX, F25):
    d.mkdir(parents=True, exist_ok=True)
OUT = HERE / "data" / "us_universe_pit.json"
OUT_V1_BAK = HERE / "data" / "us_universe_pit.v1.bak.json"
REPORT = HERE / "data" / "us_universe_rebuild_report.json"
HEADERS = {"User-Agent": "AlphaResearch-USTrack contact@alpha-research-project.example",
           "Accept-Encoding": "gzip, deflate"}
SLEEP = 0.2
STOPPED_FILING_MONTHS = 15

QUARTERS = [(y, q) for y in range(2010, 2027) for q in (1, 2, 3, 4)
            if not (y == 2026 and q == 4)]

# 普通股的證券類別字樣（裁示一.1：Common Stock／Ordinary Shares／Class A/B）。
# 比對前先轉小寫並壓空白。刻意**不**收 preferred/warrant/unit/note/bond/debenture/
# right/depositary 這些——它們正是舊版把 AAPL 等誤標下市的來源。
COMMON_PAT = re.compile(
    r"common\s*stock|common\s*shares|ordinary\s*shares|ordinary\s*stock|"
    r"class\s+[ab]\b|common\s*equity|share[s]?\s+of\s+common", re.I)
NONCOMMON_PAT = re.compile(
    r"preferred|warrant|unit[s]?\b|note[s]?\b|bond|debenture|right[s]?\b|"
    r"depositary\s+share|subordinat|trust\s+preferred|contingent\s+value", re.I)


ROW_RE = re.compile(r"^(\S+)\s+(.*?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(edgar/\S+)\s*$")


# 全域發送節流：不論幾條執行緒，整個行程合計不超過 1/SLEEP＝5 req/秒
# （SEC 官方上限 10 req/秒，專案慣例取一半）。單執行緒時網路延遲會把實際速率
# 壓到約 1.5 req/秒——那是把額度浪費掉，不是更有禮貌；用這個限速器配上少量
# 執行緒，才真的跑在「專案自訂的 5 req/秒」上。
_rate_lock = threading.Lock()
_next_slot = [0.0]


def _acquire_slot() -> None:
    """先.二十-一：改為呼叫跨行程共用限速器。行程內的 threading 版本在兩個
    Python 行程並行時會各自用滿 5 req/秒＝合計 10，剛好等於 SEC 官方上限、
    失去安全邊際；共用版以檔案為狀態，確保**合計** ≤5 req/秒。"""
    _shared_acquire_slot()


def get(url: str, cache: Path, binary: bool = False):
    if cache.exists():
        try:
            return gzip.decompress(cache.read_bytes()).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            try:
                return cache.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
    _acquire_slot()
    try:
        r = requests.get(url, headers=HEADERS, timeout=180)
    except Exception as e:  # noqa: BLE001
        print(f"  [網路失敗] {url}: {type(e).__name__}", flush=True)
        return None
    if r.status_code != 200:
        print(f"  [HTTP {r.status_code}] {url}", flush=True)
        return None
    txt = r.text
    cache.write_bytes(gzip.compress(txt.encode("utf-8", "replace")))
    return txt


# ───────── 步驟1：form.idx ─────────
def scan_index() -> dict:
    """回傳 {form25: [...], last_report: {cik: 'YYYY-MM-DD'}, names: {cik: name}}"""
    form25, last_report, first_report, names, all_ciks = [], {}, {}, {}, set()
    for y, q in QUARTERS:
        url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx"
        txt = get(url, IDX / f"form_{y}Q{q}.idx.gz")
        if txt is None:
            print(f"  {y}Q{q} 取得失敗，跳過（該季資料缺，報告中會記）", flush=True)
            continue
        n25 = 0
        for line in txt.splitlines():
            # 不用固定欄寬：form.idx 的資料列欄位起點與表頭不一致（實測 2024Q1：
            # 表頭說 Date Filed 在 86，實際資料從 91 開始），硬切會整份解析不到。
            m = ROW_RE.match(line)
            if not m:
                continue
            ft, name, cik_s, dt, fn = m.group(1), m.group(2).strip(), m.group(3), m.group(4), m.group(5)
            if ft not in ("25", "25-NSE", "10-K", "10-Q", "10-K/A", "10-Q/A"):
                continue
            cik = int(cik_s)
            all_ciks.add(cik)
            names.setdefault(cik, name)
            if ft in ("25", "25-NSE"):
                form25.append({"cik": cik, "name": name, "date": dt, "form": ft, "file": fn})
                n25 += 1
            elif ft in ("10-K", "10-Q"):  # 修正版不算 /A（原件才代表一次正式定期申報）
                if dt > last_report.get(cik, ""):
                    last_report[cik] = dt
                # first_report 是逐年母體表的關鍵：沒有它，2019 年才 IPO 的公司會被
                # 算進 2010 年的母體，整張表會**系統性高估早年檔數**，而那張表正是
                # 先.十八-二 的交付物本身。
                if cik not in first_report or dt < first_report[cik]:
                    first_report[cik] = dt
        print(f"  {y}Q{q}: Form25 {n25}、累計申報人 {len(all_ciks)}、有定期報告者 {len(last_report)}", flush=True)
    return {"form25": form25, "last_report": last_report, "first_report": first_report,
            "names": names, "all_ciks": sorted(all_ciks)}


# ───────── 步驟2：Form 25 證券類別 ─────────
SEC_CLASS_RE = re.compile(r"<(?:securityClassTitle|descriptionClassSecurity)>(.*?)"
                          r"</(?:securityClassTitle|descriptionClassSecurity)>", re.I | re.S)
# 25-NSE 由交易所代為申報，XML 裡 <issuer><cik> 才是被下市的公司；form.idx 那一列
# 記到的可能是交易所自己的 CIK（實測 NYSE＝876661 重複出現數百次）。不取 issuer CIK
# 會把所有交易所代申報的下市事件全部記到交易所頭上，等於整批遺失。
ISSUER_CIK_RE = re.compile(r"<issuer>.*?<cik>\s*(\d+)\s*</cik>", re.I | re.S)
# 2010～2010 年代中期的 Form 25 不是 XML，是 EDGARizer 產的 HTML：證券類別寫在
# 「(Description of class of securities)」這行說明文字的**正前方**。實測三筆 2010 年的
# 件都是這個形狀（例：「… principal executive offices) Common Stock (Description of
# class of securities)」）。純字串比對，抓不到就回空並標 parsed=False，不臆測。
DESC_MARK_RE = re.compile(r"\(\s*Description\s+of\s+(?:the\s+)?class(?:es)?\s+of\s+securit", re.I)
# Form 25 的固定句型是：「…of Issuer's principal executive offices) <證券類別> (Description
# of class of securities)」。**不能用「不含右括號」去界定證券類別**——證券名稱本身常帶括號
# （實測 2024 年件：「Arrow Dow Jones Global Yield ETF (GYLD)」），那樣會擷到空字串，
# 這正是第一版 15,238 筆只解析出 1,663 筆（10.9%）的原因。改成往回找地址欄的結尾。
ADDR_END_RE = re.compile(r"(?:principal\s+executive\s+offices|executive\s+offices|offices)\s*\)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
ENT_RE = re.compile(r"&#\d+;|&[a-zA-Z]+;")


def _plain_text(raw: str) -> str:
    body = raw.split("<TEXT>", 1)[-1]
    t = TAG_RE.sub(" ", body)
    t = ENT_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _titles_from_html(txt: str) -> list[str]:
    """從去標籤後的 Form 25 內文取證券類別：以「(Description of class of securities)」
    為右界，往回切到地址欄結尾「…executive offices)」為左界；找不到左界時退回取前
    150 字。抓不到就回空清單並讓呼叫端標 parsed=False，不臆測。"""
    out = []
    for m in DESC_MARK_RE.finditer(txt):
        win = txt[max(0, m.start() - 300):m.start()]
        a = None
        for am in ADDR_END_RE.finditer(win):
            a = am
        seg = win[a.end():] if a else win[-150:]
        seg = re.sub(r"_{3,}|-{3,}", " ", seg)
        seg = re.sub(r"\s+", " ", seg).strip(" .,;:-–—()")
        if seg:
            out.append(seg[:200])
    return out


def _one_form25(it: dict) -> tuple[str, dict]:
    acc = Path(it["file"]).name.replace(".txt", "")
    txt = get(f"https://www.sec.gov/Archives/{it['file']}", F25 / f"{acc}.txt.gz")
    if txt is None:
        return acc, {"cik": it["cik"], "date": it["date"], "form": it["form"],
                     "error": "fetch_failed", "parsed": False, "is_common": False}
    titles = [re.sub(r"\s+", " ", t).strip() for t in SEC_CLASS_RE.findall(txt)]
    src = "xml_class_tag"
    if not titles:
        titles = _titles_from_html(_plain_text(txt))
        src = "html_description_of_class"
    issuers = sorted({int(c) for c in ISSUER_CIK_RE.findall(txt)})
    blob = " | ".join(titles)[:1000]
    is_common = bool(COMMON_PAT.search(blob)) and not _only_noncommon(titles)
    return acc, {"cik": it["cik"], "issuer_ciks": issuers, "date": it["date"], "form": it["form"],
                 "titles": titles[:8], "is_common": is_common,
                 "parsed": bool(titles), "src": src}


def form25_classes(items: list[dict], limit: int | None = None, workers: int = 6) -> dict:
    """抓每筆 Form 25 的本文，解析證券類別字樣。回傳 {accession: {...}}

    用少量執行緒＋上面的全域限速器：合計仍是 5 req/秒，但不會讓網路延遲把速率
    壓到 1.5 req/秒。已落地快取者不佔用發送額度（get() 命中快取直接回傳）。
    """
    out = {}
    todo = items if limit is None else items[:limit]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (acc, rec) in enumerate(ex.map(_one_form25, todo), 1):
            out[acc] = rec
            if n % 1000 == 0:
                el = time.time() - t0
                print(f"  Form25 {n}/{len(todo)}（{n / max(el, 1e-9) * 60:.0f} 筆/分，"
                      f"已耗時 {el / 60:.1f} 分）", flush=True)
    return out


def _only_noncommon(titles: list[str]) -> bool:
    """每一個標題都明確是非普通股時回 True（避免「Common Stock」只出現在樣板文字裡）。"""
    hits = [t for t in titles if COMMON_PAT.search(t)]
    if not hits:
        return True
    return all(NONCOMMON_PAT.search(t) and not COMMON_PAT.search(t) for t in hits)


def main() -> int:
    args = sys.argv[1:]
    state_path = RAW / "us_universe_rebuild_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if "--index" in args:
        print("=== 步驟1：掃 form.idx 2010Q1～2026Q3 ===", flush=True)
        st = scan_index()
        state.update(st)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        print(f"Form 25／25-NSE 共 {len(st['form25'])} 筆；有定期報告的申報人 {len(st['last_report'])} 家", flush=True)
    if "--form25" in args:
        print("=== 步驟2：抓 Form 25 本文解析證券類別 ===", flush=True)
        cls = form25_classes(state["form25"])
        state["form25_classes"] = cls
        state_path.write_text(json.dumps(state), encoding="utf-8")
        n_common = sum(1 for v in cls.values() if v.get("is_common"))
        print(f"解析 {len(cls)} 筆，判定為普通股下市 {n_common} 筆", flush=True)
    if "--build" in args:
        print("=== 步驟3：合成新版名冊 ===", flush=True)
        build(state)
    if not args:
        print("需指定 --index / --form25 / --build")
        return 2
    return 0


def build(state: dict) -> None:
    cls = state.get("form25_classes", {})
    last_report = {int(k): v for k, v in state["last_report"].items()}
    first_report = {int(k): v for k, v in (state.get("first_report") or {}).items()}
    names = {int(k): v for k, v in state["names"].items()}
    # 現有 ticker 對照（只用來補 ticker 欄，不決定母體）
    tick = {}
    cur = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if cur and cur.get("schema") != "v2" and not OUT_V1_BAK.exists():
        OUT_V1_BAK.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
        print(f"  舊版已備份至 {OUT_V1_BAK.name}（不刪除、不覆蓋）", flush=True)
    # ticker 對照一律讀 v1 備份：v2 的 universe 以 CIK 為鍵，沒有 ticker 鍵，
    # 若誤讀 v2 會讓 ticker 查找全數落空（第一版驗證表因此 12 檔全報錯）。
    old = json.loads(OUT_V1_BAK.read_text(encoding="utf-8")) if OUT_V1_BAK.exists() else cur
    for t, v in (old.get("universe") or {}).items():
        if v.get("cik"):
            tick.setdefault(int(v["cik"]), t)
    # 普通股下市事件：每個 CIK 取最早的一次普通股 Form 25
    delisted = {}
    # 候選：每個 CIK 的所有「普通股 Form 25」日期
    cand: dict[int, list[str]] = {}
    for v in cls.values():
        if not v.get("is_common"):
            continue
        # 25-NSE 由交易所代申報，真正下市的是 <issuer><cik>；有 issuer 就以它為準
        for c in (v.get("issuer_ciks") or [int(v["cik"])]):
            cand.setdefault(int(c), []).append(v["date"])
    # **交易所轉板不是下市**：公司從 NYSE 轉 Nasdaq 也要申報普通股的 Form 25，
    # 但它仍在市、而且continues 繼續申報 10-K／10-Q（實測 PEP 2017、HON 2021、
    # WMT 2025 都是這種情形，第一版把這三檔誤標成下市）。判別方式：真正下市的
    # 公司會停止申報定期報告。取「最早的、且其後 GRACE_DAYS 天內不再有定期報告」
    # 的那一次 Form 25 當下市日；都不符合就不算下市。
    GRACE_DAYS = 180
    for c, dates in cand.items():
        lr = last_report.get(c)
        for d in sorted(dates):
            if lr is None or (date.fromisoformat(lr) - date.fromisoformat(d)).days <= GRACE_DAYS:
                delisted[c] = d
                break
    today = date.today()
    uni = {}
    for cik in state["all_ciks"]:
        cik = int(cik)
        lr = last_report.get(cik)
        rec = {"cik": cik, "name": names.get(cik, ""), "ticker": tick.get(cik),
               "first_periodic_report": first_report.get(cik),
               "last_periodic_report": lr, "status": "active"}
        if cik in delisted:
            rec["status"] = "delisted"
            rec["delisted_at"] = delisted[cik]
        elif lr:
            months = (today.year - int(lr[:4])) * 12 + (today.month - int(lr[5:7]))
            if months > STOPPED_FILING_MONTHS:
                rec["status"] = "stopped_filing"
                rec["stopped_filing_since"] = lr
        uni[str(cik)] = rec
    doc = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "schema": "v2",
           "source": "SEC EDGAR full-index form.idx 2010Q1～2026Q3 全量；Form 25／25-NSE 逐筆解析 securityClassTitle",
           "note": ("v2（先.十八-一）：母體改為「2010 以來曾向 SEC 申報過 10-K／10-Q 或 Form 25 的所有 CIK」，"
                    "不再從現有 ticker 名冊出發，故含早已下市、現在沒有 ticker 的公司。"
                    "delisted 只在 Form 25 的證券類別為普通股時才標；非普通股（優先股／權證／票券等）不再誤判。"
                    "另加 last_periodic_report 與 stopped_filing（>15 個月無定期報告）。"),
           "quarters_scanned": [f"{y}Q{q}" for y, q in QUARTERS],
           "stopped_filing_months": STOPPED_FILING_MONTHS,
           "counts": {}, "universe": uni}
    cnt = {"total": len(uni)}
    for s in ("active", "delisted", "stopped_filing"):
        cnt[s] = sum(1 for v in uni.values() if v["status"] == s)
    doc["counts"] = cnt
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    # 報告
    by_year = {}
    for v in uni.values():
        if v["status"] == "delisted":
            y = v["delisted_at"][:4]
            by_year.setdefault(y, {"delisted": 0, "stopped_filing": 0})["delisted"] += 1
        elif v["status"] == "stopped_filing":
            y = v["stopped_filing_since"][:4]
            by_year.setdefault(y, {"delisted": 0, "stopped_filing": 0})["stopped_filing"] += 1
    check12 = {}
    for t in ["AAPL", "WMT", "IBM", "PG", "V", "PEP", "UPS", "FDX", "LLY", "AMGN", "HON", "TMO"]:
        c = next((int(x["cik"]) for k, x in (old.get("universe") or {}).items()
                  if k == t and x.get("cik")), None)
        r = uni.get(str(c)) if c else None
        check12[t] = {"cik": c, "status": r["status"] if r else "不在新母體",
                      "ok_not_delisted": bool(r and r["status"] != "delisted")}
    sample = []
    for cikv, dt in sorted(delisted.items(), key=lambda kv: kv[1])[:20]:
        a = next((k for k, v in cls.items()
                  if v.get("is_common") and v.get("date") == dt
                  and cikv in [int(x) for x in (v.get("issuer_ciks") or [v.get("cik", -1)])]), None)
        sample.append({"cik": cikv, "name": names.get(cikv, ""), "delisted_at": dt,
                       "titles": cls.get(a, {}).get("titles"),
                       "form25_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cikv}&type=25&dateb=&owner=include&count=40"})
    rep = {"generated_at": doc["generated_at"], "counts": cnt, "by_year": dict(sorted(by_year.items())),
           "check_12_large_caps_must_not_be_delisted": check12,
           "sample_20_delisted_for_manual_audit": sample,
           "form25_total": len(cls),
           "form25_parsed": sum(1 for v in cls.values() if v.get("parsed")),
           "form25_judged_common": sum(1 for v in cls.values() if v.get("is_common"))}
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(cnt, ensure_ascii=False), flush=True)
    print(f"已寫入 {OUT} 與 {REPORT}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
