"""B30 客戶集中度——SEC「Financial Statement and Notes Data Sets」回填抽取器。

事前登記規格：`research/B30_CUSTOMER_CONCENTRATION_SPEC.md`（本檔只負責「資料」，
不碰報酬、不算任何因子績效；判定腳本另寫，且只能在回填完成後才寫）。

做什麼：
  逐期下載 SEC DERA 官方 notes 資料集 zip（2009q1～最新月檔），串流讀
  `num.tsv`，只留 tag ∈ {ConcentrationRiskPercentage1, ConcentrationRiskPercentage}
  的列（不在這裡做維度篩選，見 TAGS 註解），連同 `sub.tsv` 的
  申報日（filed，PIT 可得日）寫成小 CSV：
      research/data/b30_concentration/{period}.csv
  原始 zip 下載到系統暫存資料夾、解析完立刻刪除（每檔約 0.5GB，全期約 27GB，
  不進 repo、不長期占磁碟）。

頻率（C:\\alpha\\CLAUDE.md「SEC EDGAR」：官方上限 10 req/秒）：一個 zip 一個
請求，請求之間至少 sleep 0.2 秒；實際瓶頸是頻寬不是次數。

用法：
  python research/b30_sec_concentration_extract.py --max-files 6     # 依序補 6 期（已做過的跳過）
  python research/b30_sec_concentration_extract.py --local X.zip --period 2026_09   # 用已下載檔測試
  python research/b30_sec_concentration_extract.py --status          # 印出進度
冪等：輸出檔已存在的期別直接跳過；中斷重跑只會從沒做完的那期繼續。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 主控台不支援 reconfigure 時照常跑，只是中文可能亂碼
    print(f"[warn] reconfigure 失敗：{e}")

HERE = Path(__file__).parent
OUT_DIR = HERE / "data" / "b30_concentration"
STATUS = OUT_DIR / "_status.json"
INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets"
BASE = "https://www.sec.gov"
HEADERS = {"User-Agent": "AlphaApp-USFinancials " + (os.environ.get("ALPHA_UA_CONTACT") or "contact@alpha-app-project.example")}
SEC_SLEEP = 0.2
# 2009～2013 年左右的 us-gaap 版本用 ConcentrationRiskPercentage（無 1），2011q2 實測
# 140 列全是這個名字、0 列 ...1；維度命名也跟新版不同（例：ConcentrationRiskByType=
# ElectricIndustry），所以抽取時「不」用維度過濾，兩個 tag 全留，分類交給判定腳本
# 依規格第 2 節做（規則寫死在規格，不在這裡偷偷篩）。
TAGS = {"ConcentrationRiskPercentage1", "ConcentrationRiskPercentage"}
# 公司層級（非部門／非地區／非區間）判定：維度只能是這三個軸
COMPANY_LEVEL_KEYS = {"ConcentrationRiskByBenchmark", "ConcentrationRiskByType", "MajorCustomers"}
SUB_FIELDS = ["cik", "name", "sic", "form", "period", "fy", "fp", "filed"]
OUT_FIELDS = ["adsh", "tag", "cik", "name", "sic", "form", "period", "fy", "fp", "filed",
              "ddate", "qtrs", "value", "benchmark", "major_customer", "company_level", "segments"]


def list_zips() -> list[tuple[str, str]]:
    """回傳 [(period, url)]，由舊到新。period 例：2009q1、2026_09。"""
    r = requests.get(INDEX_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    time.sleep(SEC_SLEEP)
    hrefs = re.findall(r'href="(/files/dera/data/financial-statement-notes-data-sets/[^"]+_notes[^"]*\.zip)"', r.text)
    out = {}
    for h in hrefs:
        m = re.search(r"/(\d{4}(?:q\d|_\d{2}))_notes", h)
        if m:
            out[m.group(1)] = BASE + h
    if not out:
        raise RuntimeError("SEC 索引頁沒解析到任何 notes zip（頁面改版？）——不猜網址，直接停")
    return sorted(out.items(), key=lambda kv: kv[0].replace("_", "m"))


def _iter_tsv(z: zipfile.ZipFile, name: str):
    with z.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="")
        header = text.readline().rstrip("\r\n").split("\t")
        yield header
        for line in text:
            yield line.rstrip("\r\n").split("\t")


def parse_zip(path: Path, period: str) -> dict:
    z = zipfile.ZipFile(path)
    # 1) 維度表
    it = _iter_tsv(z, "dim.tsv")
    h = next(it)
    i_hash, i_seg = h.index("dimhash"), h.index("segments")
    dims = {p[i_hash]: p[i_seg] for p in it if len(p) > i_seg}
    # 2) num.tsv 串流過濾
    it = _iter_tsv(z, "num.tsv")
    h = next(it)
    ix = {k: h.index(k) for k in ("adsh", "tag", "ddate", "qtrs", "dimh", "value")}
    hits = []
    for p in it:
        if len(p) <= max(ix.values()) or p[ix["tag"]] not in TAGS:
            continue
        seg = dims.get(p[ix["dimh"]], "")
        kv = dict(x.split("=", 1) for x in seg.split(";") if "=" in x)
        hits.append({
            "adsh": p[ix["adsh"]], "tag": p[ix["tag"]], "ddate": p[ix["ddate"]], "qtrs": p[ix["qtrs"]],
            "value": p[ix["value"]], "benchmark": kv.get("ConcentrationRiskByBenchmark", ""),
            "major_customer": kv.get("MajorCustomers", ""),
            "company_level": int(set(kv) <= COMPANY_LEVEL_KEYS), "segments": seg,
        })
    # 3) sub.tsv 只取命中的申報
    need = {r["adsh"] for r in hits}
    it = _iter_tsv(z, "sub.tsv")
    h = next(it)
    sx = {k: h.index(k) for k in ["adsh"] + SUB_FIELDS}
    subs = {}
    for p in it:
        if len(p) > max(sx.values()) and p[sx["adsh"]] in need:
            subs[p[sx["adsh"]]] = {k: p[sx[k]] for k in SUB_FIELDS}
    z.close()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_DIR / f"{period}.csv.tmp"
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in hits:
            w.writerow({**r, **subs.get(r["adsh"], {k: "" for k in SUB_FIELDS})})
    tmp.replace(OUT_DIR / f"{period}.csv")  # 寫完才換名：中斷不會留下半份被當成已完成
    return {"period": period, "rows": len(hits), "filings": len(need),
            "missing_sub": len(need - set(subs))}


def _load_status() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"done": {}, "errors": {}}
    except Exception as e:
        print(f"[warn] 讀 {STATUS.name} 失敗，重建：{e}")
        return {"done": {}, "errors": {}}


def _save_status(st: dict) -> None:
    st["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def run(max_files: int) -> int:
    st = _load_status()
    todo = [(p, u) for p, u in list_zips() if not (OUT_DIR / f"{p}.csv").exists()]
    print(f"[b30] 待補 {len(todo)} 期，本次最多 {max_files} 期")
    tmpdir = Path(tempfile.gettempdir()) / "b30_sec_fsn"
    tmpdir.mkdir(exist_ok=True)
    for period, url in todo[:max_files]:
        dst = tmpdir / f"{period}.zip"
        t0 = time.time()
        try:
            with requests.get(url, headers=HEADERS, timeout=600, stream=True) as r:
                if r.status_code in (403, 429):
                    print(f"[b30] {period} HTTP {r.status_code}：疑似被限流，照規矩停止不重試")
                    st["errors"][period] = f"HTTP {r.status_code}"
                    _save_status(st)
                    return 2
                r.raise_for_status()
                with dst.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            time.sleep(SEC_SLEEP)
            info = parse_zip(dst, period)
            info["seconds"] = round(time.time() - t0, 1)
            st["done"][period] = info
            st["errors"].pop(period, None)
            print(f"[b30] {period} 完成：{info}")
        except Exception as e:
            print(f"[b30] {period} 失敗（記錄後換下一期）：{type(e).__name__}: {e}")
            st["errors"][period] = f"{type(e).__name__}: {e}"
        finally:
            try:
                dst.unlink(missing_ok=True)
            except Exception as e:
                print(f"[warn] 刪暫存 {dst} 失敗：{e}")
            _save_status(st)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-files", type=int, default=6)
    ap.add_argument("--local", type=Path)
    ap.add_argument("--period")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        st = _load_status()
        print(json.dumps({"done": len(st.get("done", {})), "errors": st.get("errors", {})}, ensure_ascii=False))
        return 0
    if a.local:
        if not a.period:
            ap.error("--local 需要 --period")
        info = parse_zip(a.local, a.period)
        st = _load_status()
        st["done"][a.period] = {**info, "source": "local"}
        _save_status(st)
        print(info)
        return 0
    return run(a.max_files)


if __name__ == "__main__":
    sys.exit(main())
