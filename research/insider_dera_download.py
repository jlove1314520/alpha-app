"""#75 內部人交易：SEC DERA「Insider Transactions Data Sets」季度批次檔下載＋精簡。

2026-09-19 hypothesis_queue 排程接續（#75續3「下一輪待辦(a)」）。
[自行裁量] 取代逐筆抓 Form 4 XML（實測吞吐量不可行，見 HYPOTHESIS_QUEUE.md #75續3）：
  - 官方結構化TSV，一季一個zip（約14MB），免逐筆抓XML、不受503影響。
  - 只保留非衍生證券交易列中 TRANS_CODE in {P,S}（公開市場買/賣）＋必要欄位。
  - 原始zip解析完立即刪除；輸出精簡CSV放 research/data/dera_insider/（research/data/
    已被.gitignore涵蓋，不進repo）。
  - 只下載 2006q1~2024q4（VAL_END=2024-12-31 之內），絕不碰 holdout 區間。
  - 頻率禮儀：SEC官方上限 10 req/秒；本腳本每季 1 個請求、季間 sleep 3 秒。
  - 可續跑：已存在的輸出CSV就跳過；暫時性失敗不留半成品檔。
"""
import csv
import io
import sys
import time
import zipfile
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # 守門員自身失敗不得中斷主流程（CLAUDE.md 十二）
    pass

BASE = ("https://www.sec.gov/files/structureddata/data/"
        "insider-transactions-data-sets/{y}q{q}_form345.zip")
UA = "AlphaResearch alpha-research@example.com"
HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "dera_raw"
OUT = HERE / "data" / "dera_insider"
FIRST, LAST = (2006, 1), (2024, 4)  # 2024q4 = 最後一季，<= VAL_END 2024-12-31
KEEP_CODES = {"P", "S"}

OUT_COLS = ["accession", "filing_date", "trans_date", "issuer_cik", "ticker",
            "form", "code", "shares", "price", "acq_disp", "shares_after",
            "owner_cik", "owner_rel", "owner_title"]


def quarters():
    y, q = FIRST
    while (y, q) <= LAST:
        yield y, q
        q += 1
        if q == 5:
            y, q = y + 1, 1


def read_tsv(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                                  delimiter="\t")


def process(zpath, outpath):
    z = zipfile.ZipFile(zpath)
    sub = {}
    for r in read_tsv(z, "SUBMISSION.tsv"):
        sub[r["ACCESSION_NUMBER"]] = (r["FILING_DATE"], r["ISSUERCIK"],
                                      r["ISSUERTRADINGSYMBOL"], r["DOCUMENT_TYPE"])
    trans = []
    need = set()
    for r in read_tsv(z, "NONDERIV_TRANS.tsv"):
        if r["TRANS_CODE"] in KEEP_CODES and r["ACCESSION_NUMBER"] in sub:
            trans.append(r)
            need.add(r["ACCESSION_NUMBER"])
    owner = {}
    for r in read_tsv(z, "REPORTINGOWNER.tsv"):
        a = r["ACCESSION_NUMBER"]
        if a in need and a not in owner:  # 多申報人只留第一位，欄位僅供分群用
            owner[a] = (r["RPTOWNERCIK"], r["RPTOWNER_RELATIONSHIP"], r["RPTOWNER_TITLE"])
    tmp = outpath.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_COLS)
        for r in trans:
            a = r["ACCESSION_NUMBER"]
            fd, cik, tk, dt = sub[a]
            oc, orl, ot = owner.get(a, ("", "", ""))
            w.writerow([a, fd, r["TRANS_DATE"], cik, tk, dt, r["TRANS_CODE"],
                        r["TRANS_SHARES"], r["TRANS_PRICEPERSHARE"],
                        r["TRANS_ACQUIRED_DISP_CD"], r["SHRS_OWND_FOLWNG_TRANS"],
                        oc, orl, ot])
    tmp.replace(outpath)
    return len(trans)


def main(max_quarters=None):
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    done = fail = 0
    for y, q in quarters():
        outp = OUT / f"{y}q{q}.csv"
        if outp.exists():
            continue
        if max_quarters is not None and done >= max_quarters:
            break
        zp = RAW / f"{y}q{q}.zip"
        try:
            resp = requests.get(BASE.format(y=y, q=q), headers={"User-Agent": UA},
                                timeout=180)
            if resp.status_code != 200:
                print(f"{y}q{q}: HTTP {resp.status_code}，略過（下批重試）")
                fail += 1
                time.sleep(3)
                continue
            zp.write_bytes(resp.content)
            n = process(zp, outp)
            print(f"{y}q{q}: 保留 P/S 交易 {n} 列")
            done += 1
        except Exception as e:  # 單季失敗不影響其他季，不留半成品
            print(f"{y}q{q}: 失敗 {type(e).__name__}: {e}")
            fail += 1
        finally:
            if zp.exists():
                zp.unlink()
        time.sleep(3)
    remain = sum(1 for y, q in quarters() if not (OUT / f"{y}q{q}.csv").exists())
    print(f"本次完成 {done} 季、失敗 {fail} 季、剩餘 {remain} 季")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
