"""#64（台指期貨基差/轉倉價差 TX Futures-Spot Basis / Roll Yield）地基驗證：
在進第1關cheap gate前，先確認`fut_basis_series.py::build_basis_series()`
輸出的逐日`basis_pct`欄位在#60已驗證的7個非標準到期日附近，是否確實出現
機械性收斂（結算日當天basis應貼近0，因為結算是以現貨價格為準的現金結算）。

**為什麼要做這一步（協定第2節「determinism前置檢查」精神的延伸）**：
`#64`要用的近月期貨序列跟`#60`（結算日機械效應）共用同一套
`continuous_contract.py`滾動偵測邏輯，但兩者從沒被同一支腳本交叉驗證過。
如果基礎設施本身有沒發現的日期對齊問題（例如`prev_date`錯位一天），
`#60`已經測完結案（見`HYPOTHESIS_QUEUE.md`#60），但`#64`要用的是「連續
basis水位」，錯位的影響方式不同——`#60`只看事件窗口內的報酬，一天錯位
可能被平均掉；`#64`要看每一天的basis水位本身，一天錯位就會讓「結算日
當天應該收斂到0」這個物理事實檢查不出來。用這7個已知非標準日期（不是
「每月第三個星期三」規則能算對的）當交叉驗證錨點，比隨便挑7個標準日期
更嚴格——如果連這7個「規則會算錯但反推機制正確」的日期都能在basis序列
上正確收斂，代表兩支模組的日期對齊是一致的，才有信心往下走cheap gate。

**這不是#64本身的判準，只是地基/determinism檢查**——通過或不通過都不是
PASS/FAIL，是「能不能信任這份basis資料就開始測」的前置關卡。

執行方式：`python fut_basis_settlement_alignment_probe64.py`（read-only，
零新增API呼叫——`build_basis_series()`與`derive_settlement_dates()`皆
複用既有已驗證的full-history快取；只印結果，不寫檔）。
"""
from __future__ import annotations

import pandas as pd

from fut_basis_series import build_basis_series
from fut_settlement_date_probe60 import derive_settlement_dates
from validation import holdout


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    basis = build_basis_series()
    basis = basis.sort_values("date").reset_index(drop=True)
    settle = derive_settlement_dates("TX")

    non_standard = settle[~settle["is_standard_third_wed"]].reset_index(drop=True)
    print(f"basis序列共 {len(basis)} 列，{basis['date'].min().date()}..{basis['date'].max().date()}")
    print(f"#60反推出的非標準到期日共 {len(non_standard)} 個，逐一核對basis收斂情況：\n")

    whole_sample_abs_median = basis["basis_pct"].abs().median()
    print(f"全樣本 |basis_pct| 中位數（對照基準）：{whole_sample_abs_median:.4%}\n")

    rows = []
    basis_indexed = basis.set_index("date")
    for _, r in non_standard.iterrows():
        d = pd.Timestamp(r["settlement_date"])
        if d not in basis_indexed.index:
            print(f"  {d.date()}（{r['contract_month']}）：basis序列無此日期，跳過（inner join可能因假日對齊丟掉）")
            continue
        row = basis_indexed.loc[d]
        # basis序列的 close 是「當下前月合約」，結算當天前月合約仍是即將
        # 到期的那一口（rollover在隔天才切到新前月），所以結算日當天的
        # basis_pct 理論上應貼近0（現金結算價=現貨價）。
        bp = float(row["basis_pct"])
        rows.append(dict(settlement_date=d.date(), contract_month=r["contract_month"],
                          weekday=r["weekday"], basis_pct=bp))
        flag = "收斂（<中位數）" if abs(bp) < whole_sample_abs_median else "**未收斂（>=中位數，需留意）**"
        print(f"  {d.date()}（{r['contract_month']}，{r['weekday']}）：basis_pct={bp:+.4%}  {flag}")

    df = pd.DataFrame(rows)
    n_converged = int((df["basis_pct"].abs() < whole_sample_abs_median).sum()) if not df.empty else 0
    print(f"\n7個非標準到期日中，{n_converged}/{len(df)} 天basis_pct絕對值小於全樣本中位數。")

    # 對照組：隨機抽7個「非結算日」的一般交易日，看它們的|basis_pct|
    # 是否明顯高於結算日（驗證「結算日特別收斂」不是全樣本本來就很小）。
    settle_dates_all = set(pd.to_datetime(settle["settlement_date"]))
    non_settle = basis[~basis["date"].isin(settle_dates_all)]
    sample_non_settle = non_settle.sample(n=7, random_state=20260909)
    print("\n對照：隨機抽7個一般交易日（非結算日）的|basis_pct|：")
    print(sample_non_settle[["date", "basis_pct"]].to_string(index=False,
          formatters={"basis_pct": "{:+.4%}".format}))
    print(f"\n對照組|basis_pct|平均：{sample_non_settle['basis_pct'].abs().mean():.4%} "
          f"vs 7個非標準結算日|basis_pct|平均：{df['basis_pct'].abs().mean():.4%}"
          if not df.empty else "")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
