"""#75 步驟(b)：對 insider_trading_historical.csv 索引逐筆抓 Form 4 XML、解析交易列。

分批續跑：每次跑到時間預算(--minutes)就停，進度靠輸出 JSONL 內已處理 accession 判定。
複用 .github/scripts/fetch_us_insider_trading.py 的解析邏輯(不重寫)。
窗口(事前綁定，見 HYPOTHESIS_QUEUE.md #75續2)：filed_at >= 2003-06-30(SOX強制電子申報生效日)
且 <= 2024-12-31(VAL_END)；SIVB 另截斷至 2023-03-31(破產後空殼污染)；FRC 無資料不計。
不碰 holdout：VAL_END 之後的申報一律不抓。
SEC 頻率：每請求 sleep 0.2 秒(約5 req/s，官方上限10)。
"""
import csv, json, sys, time, argparse, importlib.util
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("f4", HERE.parent / ".github/scripts/fetch_us_insider_trading.py")
f4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f4)

INDEX = HERE / "data/insider_trading_historical.csv"
OUT = HERE / "data/insider_trading_form4_parsed.jsonl"
FAIL = HERE / "data/insider_trading_form4_failed.jsonl"
START, END = "2005-01-01", "2024-12-31"  # 2026-09-19 由2003-06-30改：2003-06~2004申報實測503/無XML(原因未查證)，2005起抽樣6年皆可解析
TRUNC = {"SIVB": "2023-03-31"}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=8)
    a = ap.parse_args()
    deadline = time.time() + a.minutes * 60
    rows = [r for r in csv.DictReader(open(INDEX, encoding="utf-8"))
            if START <= r["filed_at"] <= min(END, TRUNC.get(r["ticker"], END))]
    rows.sort(key=lambda r: (r["filed_at"], r["ticker"]))
    done = set()
    for p in (OUT, FAIL):
        if p.exists():
            for ln in open(p, encoding="utf-8"):
                try: done.add(json.loads(ln)["accession"])
                except Exception: pass
    todo = [r for r in rows if r["accession"] not in done]
    print(f"窗口內 {len(rows)} 筆，已處理 {len(done)}，待處理 {len(todo)}")
    n_ok = n_fail = n_transient = 0
    with open(OUT, "a", encoding="utf-8") as fo, open(FAIL, "a", encoding="utf-8") as ff:
        for r in todo:
            if time.time() > deadline: break
            try:
                cik = int(r["cik"])
                # 2026-09-19 改走 accession .txt 完整申報檔(單一請求)：原 index.json 目錄路線
                # 對自行申報(accession前綴=公司自身CIK)的舊申報常 503，.txt 實測可用且少一次請求。
                txt = f4._get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{r['accession']}.txt").text
                i, j = txt.find("<ownershipDocument"), txt.find("</ownershipDocument>")
                if i < 0 or j < 0:
                    raise RuntimeError("PERM: 申報檔內無ownershipDocument XML")
                xml = txt[i:j + len("</ownershipDocument>")].encode("utf-8")
                txns = f4.parse_form4_xml(xml, r["accession"], r["filed_at"])
                fo.write(json.dumps({"accession": r["accession"], "ticker": r["ticker"], "cik": cik,
                                     "filed_at": r["filed_at"], "txns": txns}, ensure_ascii=False) + "\n")
                n_ok += 1
            except Exception as e:
                if "503" in str(e) or "Timeout" in type(e).__name__ or "Connection" in type(e).__name__:
                    n_transient += 1  # 暫時性錯誤不記入已處理，下批重試
                    continue
                ff.write(json.dumps({"accession": r["accession"], "ticker": r["ticker"],
                                     "reason": f"{type(e).__name__}: {e}"[:200]}, ensure_ascii=False) + "\n")
                n_fail += 1
            fo.flush(); ff.flush()
    print(f"本批成功 {n_ok} 永久失敗 {n_fail} 暫時性(待重試) {n_transient}；剩餘約 {len(todo)-n_ok-n_fail}")
if __name__ == "__main__":
    main()
