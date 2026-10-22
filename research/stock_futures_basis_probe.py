"""補.研究-個股期貨基差：第 10 關「資料源歷史起點探測」（只印日期與契約清單，不算任何報酬）。

來源：期交所「期貨每日交易行情下載」歷史年度檔
  POST https://www.taifex.com.tw/cht/3/futDataDown  down_type=2&his_year=YYYY（zip、Big5 CSV）
  同一端點已在 docs/PREREG_overnight_intraday_1999_2009_FINAL.md 用過（robots.txt 404、官方未公布上限）。
節流：重用 research/paper_5_vrp_tracker.py 的 _get()，來源名 taifex_www，
  與 data/rate_limit_state.json 共用（同源 ≥3 秒、402/403/428/429 封鎖 2 小時不重試）。
快取：research/data/raw/taifex_fut_yearly/{年}.zip（已存在就不重抓；不進公開 repo）。

用法：
  python research/stock_futures_basis_probe.py 2010        # 抓（若無快取）並探測 2010 年度檔
  python research/stock_futures_basis_probe.py 2010 --no-fetch
"""
from __future__ import annotations

import collections
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
RAW = ROOT / "research" / "data" / "raw" / "taifex_fut_yearly"
URL = "https://www.taifex.com.tw/cht/3/futDataDown"
# 指數／商品類期貨代號（不是個股期貨）；個股期貨代號是三碼、以 F 結尾（例 CDF＝台積電期貨），
# 這裡只做描述性分類，最後以 TAIFEX 契約名冊核對為準（PREREG 階段再做）。
NON_STOCK = {"TX", "MTX", "TE", "TF", "XIF", "GTF", "T5F", "TJF", "GDF", "TGF", "RHF", "RTF",
             "BTF", "E4F", "SOF", "SHF", "SXF", "UDF", "SPF", "UNF", "F1F", "G2F", "TMF", "UJF",
             "UAF", "UEF", "XAF", "XBF", "XEF", "XJF", "BRF", "NYF", "XUF", "TXO"}


def fetch(year: int) -> Path:
    f = RAW / f"{year}.zip"
    if f.exists():
        return f
    from paper_5_vrp_tracker import _get  # 共用節流（同源 ≥3 秒、封鎖碼即停）
    RAW.mkdir(parents=True, exist_ok=True)
    r = _get("taifex_www", "POST", URL, data={"down_type": "2", "his_year": str(year)})
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        raise SystemExit(f"{year} 年度檔不是 zip（HTTP {r.status_code}、{len(r.content)} bytes），不寫快取")
    f.write_bytes(r.content)
    return f


def probe(f: Path) -> dict:
    first = {}
    last = {}
    rows = collections.Counter()
    sessions = collections.Counter()
    header = None
    with zipfile.ZipFile(f) as z:
        for n in z.namelist():
            text = z.read(n).decode("big5", errors="replace")
            lines = text.splitlines()
            if header is None and lines:
                header = lines[0]
            for ln in lines[1:]:
                p = [x.strip() for x in ln.split(",")]
                if len(p) < 7:
                    continue
                code, dt = p[1], p[0].replace("/", "-")
                if len(p) > 17:
                    sessions[p[17]] += 1
                rows[code] += 1
                first[code] = min(first.get(code, dt), dt)
                last[code] = max(last.get(code, dt), dt)
    stock = sorted(c for c in rows if c not in NON_STOCK)
    return {
        "file": f.name,
        "header": header,
        "n_contract_codes": len(rows),
        "n_stock_like_codes": len(stock),
        "stock_like_earliest": min((first[c] for c in stock), default=None),
        "stock_like_first_dates": {c: first[c] for c in stock[:40]},
        "non_stock_codes_seen": sorted(c for c in rows if c in NON_STOCK),
        "sessions": dict(sessions),
        "rows_total": sum(rows.values()),
    }


def main() -> int:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2010
    f = RAW / f"{year}.zip" if "--no-fetch" in sys.argv else fetch(year)
    print(json.dumps(probe(f), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
