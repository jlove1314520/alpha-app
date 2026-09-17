# audit_e_pe_diagnosis.py — 總司令裁示【稽核.五：季報回補的數字本身可能是錯的】查證腳本。
#
# 只查不改（總司令原話「只查不改，回報後再裁示」），本檔案不修改任何 data/*.json。
#
# 背景：data_audit.py 的 e_pe 檢查（近四季 EPS 推算的隱含本益比 vs 官方 PER，
# 差 >10% 判違規）checked 151→395、violations 3→77，比率 2.0%→19.5%。這裡查證
# 這 77 筆到底是「基準不同（官方用不同期間）」還是「我們的 EPS 拼錯」。
#
# 方法：用「淨利/EPS 反推隱含股數」做內部一致性檢查——同一檔股票四季的隱含股數
# 理論上該接近（除非真的增減資），若某一季暴跌到其他季的千分之一量級，代表
# net_income_parent 或 eps 至少有一個欄位在那一季被錯誤解析，不是基準期間問題
# 能解釋的量級。全體/e_pe違規組的比對用更快的「最新一季 revenue < 前一季 1/50」
# 當代理指標（不保證每一筆都跟 eps 矛盾，只當強烈相關的紅旗，見結論的信心等級）。
#
# 查證結果與根因懷疑寫在 PENDING_QUEUE.md 2026-09-18 條目【資料層】稽核.五，
# 本檔案只留可重跑的查證邏輯本身。

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK_DETAIL = ROOT / "data" / "stock_detail.json"
AUDIT_REPORT = ROOT / "data" / "audit_report.json"

# 總司令指定必查：1506正道、2329華泰；另補8檔湊滿10檔樣本（77筆e_pe違規清單
# 按代號排序取前10筆，含上述兩檔）。
SAMPLE_CODES = ["1506", "1522", "2329", "2348", "2442", "2534", "2545", "2547", "2597", "2603"]


def implied_shares_by_quarter(quarters: list[dict]) -> None:
    for q in quarters:
        ni, eps = q.get("net_income_parent"), q.get("eps")
        implied = (ni / eps) if (eps not in (None, 0) and ni is not None) else None
        print(f"    {q.get('year')}Q{q.get('quarter')}  revenue={q.get('revenue')!r:>16}  "
              f"net_income_parent={ni!r:>16}  eps={eps!r:>7}  隱含股數={implied}")


def sample_diagnosis() -> None:
    sd = json.loads(STOCK_DETAIL.read_text(encoding="utf-8"))
    stocks = sd.get("stocks", {})
    print("=== 10檔抽驗（近四季 revenue/net_income_parent/eps + 隱含股數一致性）===")
    for code in SAMPLE_CODES:
        d = stocks.get(code, {})
        qs = (d.get("financials") or {}).get("quarters") or []
        print(f"\n---- {code} ----")
        implied_shares_by_quarter(qs[-4:])


def scope_estimate() -> None:
    sd = json.loads(STOCK_DETAIL.read_text(encoding="utf-8"))
    stocks = sd.get("stocks", {})

    def hits(codes: list[str] | None) -> tuple[int, int]:
        checked = bug = 0
        pool = codes if codes is not None else list(stocks.keys())
        for c in pool:
            d = stocks.get(c, {})
            qs = (d.get("financials") or {}).get("quarters") or []
            last4 = qs[-4:]
            if len(last4) < 4:
                continue
            revs = [q.get("revenue") for q in last4]
            if any(x is None or x <= 0 for x in revs):
                continue
            checked += 1
            if revs[-1] < revs[-2] / 50:
                bug += 1
        return checked, bug

    report = json.loads(AUDIT_REPORT.read_text(encoding="utf-8"))
    e_pe_codes = [v["code"] for v in report.get("violations", []) if v["check"] == "e_pe"]
    checked_all, bug_all = hits(None)
    checked_epe, bug_epe = hits(e_pe_codes)
    print("\n=== 規模估計：最新一季 revenue < 前一季 1/50 的比例 ===")
    print(f"全體 stock_detail.json 可比對股票：{bug_all}/{checked_all} "
          f"（{bug_all / checked_all * 100:.1f}%，基準比例）")
    print(f"e_pe 違規組（{len(e_pe_codes)} 筆）：{bug_epe}/{checked_epe} "
          f"（{bug_epe / checked_epe * 100:.1f}%，e_pe違規組命中率）")


if __name__ == "__main__":
    sample_diagnosis()
    scope_estimate()
