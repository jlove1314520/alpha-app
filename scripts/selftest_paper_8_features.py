# -*- coding: utf-8 -*-
"""自測：模擬 H 前向價量特徵（paper_8_ml_tracker.price_features）與訓練用 factors.prepare_factors 數值一致。

只讀本機 FinMind 快取（離線模式，與訓練面板同一套），在 2010～2024 年歷史資料上逐日比對 10 個價量特徵＋3 個三大法人特徵，
容許誤差 1e-9（相對）。不碰 holdout（load_dev 上限 2024-12-31）。
用法：python scripts/selftest_paper_8_features.py [代號…]（預設 2330 2317 1101）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np  # noqa: E402
import paper_8_ml_tracker as P  # noqa: E402


def main(ids):
    P._offline_guard()
    import factors
    from adjust import adjusted_price_series
    from finmind_client import load_dev
    from strategies.weinstein_stage2 import prepare_market_data

    m = prepare_market_data(load_dev("TaiwanStockPrice", "TAIEX", P.FACTOR_START))
    mkt = dict(zip(m["date"], m["close"]))
    bad = 0
    for sid in ids:
        px = adjusted_price_series(sid, P.FACTOR_START)
        ref = factors.prepare_factors(sid, px, m, P.FACTOR_START).sort_values("date").reset_index(drop=True)
        got = P.price_features(px, mkt)
        for c in P.PRICE_FEATURES:
            a = ref[c].to_numpy(dtype=float)
            b = got[c].to_numpy(dtype=float)
            same_nan = np.array_equal(np.isnan(a), np.isnan(b))
            ok = np.isfinite(a) & np.isfinite(b)
            maxrel = float(np.max(np.abs(a[ok] - b[ok]) / np.maximum(np.abs(a[ok]), 1e-12))) if ok.any() else 0.0
            flag = same_nan and maxrel < 1e-9
            bad += not flag
            print(f"{sid} {c:26s} 非NaN={int(ok.sum()):5d} NaN位置一致={same_nan} 最大相對誤差={maxrel:.2e} {'OK' if flag else 'FAIL'}")
        # 三大法人 3 個（先.一三〇-1 ①）：把訓練用的 T86/FinMind 股數轉成前向檔案的「張」格式，
        # 外資用訓練口徑（不含外資自營商），確認 inst_features 與 prepare_factors 公式一致。
        # 參照值套用訓練面板同一條「當天無法人原始列 → NaN」規則；前向另有「前 20 日缺班 → NaN」，
        # 歷史資料沒有缺班，只會讓 inst 起點後前 19 天多出 NaN，所以只比對兩邊都有值的列＋數 NaN 差。
        inst = factors._institutional_daily_net(sid, P.FACTOR_START)
        inst_d = {str(r.date)[:10].replace("-", ""): [r.foreign_net / 1000, r.trust_net / 1000,
                                                        (r.total_net - r.foreign_net - r.trust_net) / 1000]
                  for r in inst.itertuples()}
        keys = [str(x)[:10].replace("-", "") for x in ref["date"]]
        # 前向的 inst_dates 是「全市場有收錄的日子」；歷史上 T86 每個交易日都有，取該檔第一筆法人列之後的所有交易日
        first = min(inst_d) if inst_d else "99999999"
        got_i = P.inst_features(px, inst_d, {k for k in keys if k >= first})
        no_inst = np.array([k not in inst_d for k in keys])
        for c in P.INST_FEATURES:
            a = ref[c].to_numpy(dtype=float).copy()
            a[no_inst] = np.nan
            b = got_i[c].to_numpy(dtype=float)
            ok = np.isfinite(a) & np.isfinite(b)
            extra_nan = int((np.isfinite(a) & ~np.isfinite(b)).sum())
            wrong_val = int((~np.isfinite(a) & np.isfinite(b)).sum())
            maxrel = float(np.max(np.abs(a[ok] - b[ok]) / np.maximum(np.abs(a[ok]), 1e-12))) if ok.any() else 0.0
            flag = ok.sum() > 1000 and maxrel < 1e-6 and wrong_val == 0 and extra_nan <= 19
            bad += not flag
            print(f"{sid} {c:26s} 非NaN={int(ok.sum()):5d} 前向多NaN={extra_nan} 前向多值={wrong_val} 最大相對誤差={maxrel:.2e} {'OK' if flag else 'FAIL'}")
    print("全部一致" if not bad else f"FAIL {bad} 項")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["2330", "2317", "1101"]))
