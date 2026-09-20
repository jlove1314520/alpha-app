"""#75續12：G0-c 悲觀邊界填補規則（依續10 SPEC事前綁定）＋合成資料單元自測。
只實作規則與自測；不讀任何真實報酬、零外部請求。第1關報酬計算留給下一輪。
規則：買入月的發行人無價格(no_price)，且其DERA最後申報月 < 樣本終點(2024-12)（代理「已下市/消失」），
其後20日報酬 = 該月橫斷面「最差十分位」報酬（有價格者報酬的10%分位數）。
無價格但最後申報月>=樣本終點者(仍在申報，只是ticker對不上)：不填補、不納入(版本ii中剔除並計缺口)。
誠實但書：『最後申報月』是內部人申報的最後月，非真正下市日，僅為代理；已下市股7.1%無價格來源但書照舊。"""
import sys
import numpy as np, pandas as pd
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SAMPLE_END = "2024-12"

def pessimistic_fill(panel: pd.DataFrame, last_filing_month: dict, q: float = 0.10):
    """panel欄位: month, issuer_cik, fwd20(有價格者=報酬, 無價格者=NaN)。
    回傳 (版本i樂觀=僅有價格者, 版本ii悲觀=填補後, 缺口統計dict)。"""
    p = panel.copy()
    has = p["fwd20"].notna()
    opt = p[has].copy()
    worst = p[has].groupby("month")["fwd20"].quantile(q)          # 每月橫斷面最差十分位
    p["last"] = p["issuer_cik"].map(last_filing_month)
    dead = (~has) & (p["last"].notna()) & (p["last"] < SAMPLE_END)
    live_noprice = (~has) & ~dead
    pes = p[has | dead].copy()
    fill = pes["fwd20"].isna()
    pes.loc[fill, "fwd20"] = pes.loc[fill, "month"].map(worst)
    pes = pes[pes["fwd20"].notna()]                                 # 該月無有價格者→worst為NaN→無法填補，剔除並計缺口
    n_filled = int(fill.loc[pes.index].sum())                        # 剔除後仍在pes且原本無價格者(實際已填補)
    gap = {"n_total": int(len(p)), "n_priced": int(has.sum()), "n_filled": n_filled,
           "n_live_noprice_dropped": int(live_noprice.sum()),
           "n_dead_unfillable_month": int(dead.sum()) - n_filled}
    return opt.drop(columns=["last"], errors="ignore"), pes.drop(columns=["last"], errors="ignore"), gap

def _selftest():
    rng = np.random.default_rng(0)
    rows = []
    for m in ["2019-01", "2019-02"]:
        for i in range(20):                                        # 20 檔有價格，報酬 -0.19..0.19
            rows.append((m, f"P{i}", (i - 10) / 50))
        rows += [(m, "DEAD", np.nan), (m, "LIVE", np.nan)]         # 一檔已消失、一檔仍在申報但無價格
    panel = pd.DataFrame(rows, columns=["month", "issuer_cik", "fwd20"])
    last = {**{f"P{i}": "2024-12" for i in range(20)}, "DEAD": "2019-06", "LIVE": "2024-12"}
    opt, pes, gap = pessimistic_fill(panel, last)
    want = float(np.quantile([(i - 10) / 50 for i in range(20)], 0.10))
    d = pes[pes["issuer_cik"] == "DEAD"]["fwd20"]
    assert len(opt) == 40 and opt["fwd20"].notna().all(), "版本i只含有價格者"
    assert len(d) == 2 and np.allclose(d, want), f"DEAD應以最差十分位{want}填補，得{list(d)}"
    assert "LIVE" not in set(pes["issuer_cik"]), "仍在申報但無價格者不得填補"
    assert gap["n_filled"] == 2 and gap["n_live_noprice_dropped"] == 2
    assert pes["fwd20"].mean() < opt["fwd20"].mean(), "悲觀版平均必須低於樂觀版"
    # 邊界：某月完全無有價格者→無法填補，須剔除而非拋錯
    p2 = pd.DataFrame([("2020-01", "D2", np.nan), ("2020-01", "P", 0.05)], columns=panel.columns)
    p2 = pd.concat([p2, pd.DataFrame([("2020-02", "D2", np.nan)], columns=panel.columns)])
    _, pes2, _ = pessimistic_fill(p2, {"D2": "2020-03", "P": "2024-12"})
    assert set(pes2["month"]) == {"2020-01"}, "無有價格者的月份應剔除"
    print("SELFTEST_OK", {"worst_decile": round(want, 4), "opt_mean": round(opt["fwd20"].mean(), 4), "pes_mean": round(pes["fwd20"].mean(), 4)}, gap)

if __name__ == "__main__":
    _selftest()
