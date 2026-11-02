"""先.一三五-1ih：現金流量表摘要（`scripts/build_cash_flow_json.py`）合成自測（零外部請求）。

這支只讀本機 FinMind 研究快取（gitignore），快取不在的機器上跑會產生 0 檔的空表；原本照樣蓋掉
`data/cash_flow.json`（App 個股頁現金流卡、`build_by_code.py` 的來源），且某檔只有資本支出、沒有營業
現金流時 `max()` 空序列會讓整支中斷。1ih 已修（純 bug 修復）。本自測：
  ① TTM：最新為 Q4 → 全年；非 Q4 → 最新累計＋上年全年−上年同季
  ② 缺上年同季 → 不算（略過、記原因）
  ③ 正常快取 → 寫出、FCF＝CFO＋CAPEX
  ④ 只有資本支出的檔 → 只略過那一檔、其他照算，不中斷
  ⑤ 讀不到的檔 → 記「快取檔讀取失敗」、其他照算；FinMind 回空的檔另記「快取為空」（1ii）
  ⑥ 快取完全不在 → 回非 0、不覆寫既有輸出
用暫存目錄，不讀 data/、不連網。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cash_flow_json as B  # noqa: E402

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"：{detail}" if detail else ""))


def write_cache(raw: Path, code: str, rows: list[tuple[str, str, float]]) -> None:
    pd.DataFrame(rows, columns=["date", "type", "value"]).to_parquet(
        raw / f"TaiwanStockCashFlowsStatement__{code}__x__latest.parquet")


def run(raw: Path, out: Path) -> int:
    B.RAW, B.OUT = raw, out
    return B.main()


C, K = B.CFO, B.CAPEX
cum = {"2026-06-30": {C: 60.0}, "2025-12-31": {C: 100.0}, "2025-06-30": {C: 40.0}, "2024-12-31": {C: 90.0}}
check("① Q4 → 全年", B.ttm(cum, C, "2025-12-31") == 100.0)
check("① 非 Q4 → 60＋100−40＝120", B.ttm(cum, C, "2026-06-30") == 120.0)
check("② 缺上年同季 → None", B.ttm({"2026-03-31": {C: 5.0}, "2025-12-31": {C: 9.0}}, C, "2026-03-31") is None)

with tempfile.TemporaryDirectory() as td:
    raw, out = Path(td) / "raw", Path(td) / "cash_flow.json"
    raw.mkdir()
    write_cache(raw, "1111", [("2025-12-31", C, 100.0), ("2025-12-31", K, -30.0)])
    write_cache(raw, "2222", [("2025-12-31", K, -5.0)])  # 只有資本支出
    (raw / "TaiwanStockCashFlowsStatement__3333__x__latest.parquet").write_bytes(b"not parquet")
    pd.DataFrame().to_parquet(raw / "TaiwanStockCashFlowsStatement__4444__x__latest.parquet")  # FinMind 回空
    rc = run(raw, out)
    d = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    s = d.get("stocks", {})
    check("③ 正常快取寫出", rc == 0 and s.get("1111", {}).get("fcf_ttm") == 70, f"rc={rc} 1111={s.get('1111')}")
    check("④ 只有資本支出 → 只略過那檔", "2222" not in s and d.get("skipped", {}).get("無營業現金流欄位") == 1,
          str(d.get("skipped")))
    check("⑤ 讀不到的檔 → 記原因、其他照算", d.get("skipped", {}).get("快取檔讀取失敗") == 1 and d.get("count") == 1)
    check("⑤-1 空快取 → 記「快取為空」不算讀取失敗", d.get("skipped", {}).get("快取為空（FinMind 無資料）") == 1)

    empty = Path(td) / "empty"
    empty.mkdir()
    before = out.read_bytes()
    rc = run(empty, out)
    check("⑥ 快取不在 → 非 0、不覆寫", rc != 0 and out.read_bytes() == before, f"rc={rc}")

print(f"結果：{sum(results)}／{len(results)} PASS")
sys.exit(0 if all(results) else 1)
