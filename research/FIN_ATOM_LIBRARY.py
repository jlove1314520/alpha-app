"""原子.四：財報原子與算子庫（`PENDING_QUEUE.md`「2026-09-20補入項目」
【裁示】原子.二FAIL採信，轉財報原子家族）。

**定位**：與價量原子庫`ATOM_LIBRARY.py`並存、互不 import。價量原子的輸入是
日頻OHLCV，這裡的輸入是**季頻**財報，時間軸不同，所以獨立成一支模組。本檔
**不組任何表達式、不算任何IC、不做任何策略判定**，那是`原子.五`的範圍。

**資料源**：FinMind `TaiwanStockFinancialStatements`（損益表，單季值）、
`TaiwanStockBalanceSheet`（資產負債表，時點值）、`TaiwanStockCashFlowsStatement`
（現金流量表，**年初至今累計值**，本模組還原成單季）。載入一律走
`finmind_client.load_dev()`，於擷取層就截在VAL_END，不碰HOLDOUT。

**PIT鐵律（本檔最重要的一段）**：
- 每一季的可得日`pit_date`＝**法定申報期限**，不是財報期別日。第1~3季＝
  期末後45日（5/15、8/14、11/14）；**第4季（年報）＝次年3/31**（證交法§36：
  年報3個月內、季報45日內；來源：全國法規資料庫
  <https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode=G0400001&flno=36>）。
- **既有`pit.py`對所有季度一律用「期末+45日」，第4季會提早到2/14——但年報法定
  期限是3/31，約6週的前視偏誤**（本輪發現，未動`pit.py`，登記在
  `ATOM_LIBRARY.md`「財報原子庫」一節，交由總司令裁示是否回頭檢視既有引用
  `quarterly_pit()`的因子）。本檔自行實作正確版本。
- 2012年（含）以前的期別，舊制期限較寬（我所知：年報4個月、半年報2個月），
  **統一取保守（較晚）日期**：Q4→4/30、Q2→8/31、Q1/Q3不變。較晚只會損失時效、
  不會製造前視。**這條舊制期限未逐條查證原始法條，僅為保守估計**。
- FinMind沒有真實申報日欄位，所以`pit_source`永遠標`assumed_statutory`；公司
  通常早於期限申報，用期限＝保守（不會偷看未來），代價是訊號進場偏晚。
- **財報重編的已知限制**：FinMind每個(期別,科目)只存**最新版本**，重編後的數字
  會出現在原始`pit_date`，有輕微前視，本庫無法修正（沒有版本歷史），
  `build_quarter_frame`遇到重複列時取**最後一列**（確定性行為，有單元測試）。

**窗口限制**：財報算子的窗口`n`只准用`{1,4,8}`季，超出直接`ValueError`
（比價量庫更嚴：這裡在程式層強制，不靠呼叫端自律）。

**季度不連續**：所有「往前k季」的運算都是依**曆法季度鍵**查找，不是位置
位移；缺一季就是NaN，不會把不相鄰的兩季當成相鄰。

**NaN語意**（比照原子.一）：能算但結果無意義→NaN，不回0。基期≤0（虧損/零）
的成長率無意義→NaN；分母≤0的佔比無意義→NaN。

用法：
    python research/FIN_ATOM_LIBRARY.py --self-test   # 單元測試（純合成資料，不連網）
    python research/FIN_ATOM_LIBRARY.py --real-data   # 另加2330真實資料煙霧測試（讀本機快取）
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

try:  # 比照其他腳本：Windows cp950主控台印不出特殊符號時降級，不崩潰
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 - 守門員自身失敗只降級，見CLAUDE.md第十二節
    pass

ALLOWED_FIN_WINDOWS = (1, 4, 8)

# =============================================================================
# PIT：法定申報期限
# =============================================================================

def statutory_pit_date(period_end) -> pd.Timestamp:
    """期別日 → 保守可得日（法定申報期限）。見檔頭說明。"""
    pe = pd.Timestamp(period_end)
    q = (pe.month - 1) // 3 + 1
    y = pe.year
    if q == 4:
        # 年報：現行3個月（次年3/31）；2012年以前取舊制4個月（保守）
        return pd.Timestamp(y + 1, 3, 31) if y >= 2013 else pd.Timestamp(y + 1, 4, 30)
    if q == 1:
        return pd.Timestamp(y, 5, 15)
    if q == 2:
        return pd.Timestamp(y, 8, 14) if y >= 2013 else pd.Timestamp(y, 8, 31)
    return pd.Timestamp(y, 11, 14)


def _quarter_key(ts) -> int:
    """曆法季度序號（year*4 + q-1），用來做「往前k季」的精確查找。"""
    ts = pd.Timestamp(ts)
    return ts.year * 4 + (ts.month - 1) // 3


# =============================================================================
# 原子（11個，零參數）：欄位對應
# =============================================================================
# 損益表（單季值）：revenue/eps/gross_profit/op_income/net_income
# 資產負債表（時點值）：total_assets/equity/inventory/receivable
# 現金流量表（累計值→還原單季）：ocf
# 衍生：shares（加權平均股數＝歸屬母公司淨利/EPS）

FLOW_ATOMS = ("revenue", "eps", "gross_profit", "op_income", "net_income", "ocf", "shares")
STOCK_ATOMS = ("total_assets", "equity", "inventory", "receivable")
ATOM_NAMES = ("revenue", "eps", "gross_profit", "op_income", "net_income",
              "total_assets", "equity", "inventory", "receivable", "ocf", "shares")

# FinMind命名地雷（見build_stock_financials_history.py檔頭）：損益表裡的
# EquityAttributableToOwnersOfParent＝「淨利歸屬母公司業主」，資產負債表裡的
# 同名type才是「權益」。兩邊各自取，絕對不能混。
_INCOME_TYPES = {
    "revenue": "Revenue",
    "eps": "EPS",
    "gross_profit": "GrossProfit",
    "op_income": "OperatingIncome",
    "net_income": "EquityAttributableToOwnersOfParent",
}
_BALANCE_TYPES = {
    "total_assets": "TotalAssets",
    "equity": "EquityAttributableToOwnersOfParent",
    "inventory": "Inventories",
    "receivable": "AccountsReceivableNet",
}
# 現金流量表：兩個type語意相同（營業活動淨現金），前者2012起、後者2022起，
# 取前者、缺才退回後者（同一期若兩者都有，前者優先，不混加）。
_CASH_TYPES = ("CashFlowsFromOperatingActivities", "NetCashInflowFromOperatingActivities")


def _wide(long: pd.DataFrame | None, type_map: dict[str, str]) -> pd.DataFrame:
    """長表(date,type,value) → 以期別日為索引、欄位為原子名的寬表。
    同一(date,type)重複（財報重編）→取最後一列。缺科目→整欄NaN。"""
    idx_name = "period_end"
    if long is None or len(long) == 0:
        return pd.DataFrame(columns=list(type_map), index=pd.DatetimeIndex([], name=idx_name), dtype=float)
    d = long.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.drop_duplicates(subset=["date", "type"], keep="last")
    piv = d.pivot(index="date", columns="type", values="value")
    out = pd.DataFrame(index=piv.index)
    for atom, typ in type_map.items():
        out[atom] = piv[typ].astype(float) if typ in piv.columns else np.nan
    out.index.name = idx_name
    return out


def _decumulate_ocf(long: pd.DataFrame | None) -> pd.Series:
    """現金流量表累計值→單季：Q1=累計值；Q2~Q4=本季累計−**同會計年度上一季**累計。
    上一季缺（季度不連續）→NaN，不用更早的季度硬湊。"""
    if long is None or len(long) == 0:
        return pd.Series(dtype=float, name="ocf")
    d = long.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.drop_duplicates(subset=["date", "type"], keep="last")
    piv = d.pivot(index="date", columns="type", values="value")
    ytd = pd.Series(np.nan, index=piv.index, dtype=float)
    for typ in _CASH_TYPES:
        if typ in piv.columns:
            ytd = ytd.fillna(piv[typ].astype(float))
    ytd = ytd.sort_index()
    by_key = {_quarter_key(ix): v for ix, v in ytd.items()}
    out = {}
    for ix, v in ytd.items():
        q = (ix.month - 1) // 3 + 1
        if q == 1:
            out[ix] = v
        else:
            prev = by_key.get(_quarter_key(ix) - 1, np.nan)
            out[ix] = v - prev if pd.notna(v) and pd.notna(prev) else np.nan
    s = pd.Series(out, dtype=float, name="ocf")
    s.index.name = "period_end"
    return s


def build_quarter_frame(income: pd.DataFrame | None, balance: pd.DataFrame | None,
                        cash: pd.DataFrame | None) -> pd.DataFrame:
    """三張FinMind長表 → 單一股票的季度寬表。
    索引：`period_end`（升冪）；欄位：11個原子＋`pit_date`＋`pit_source`。
    **任何跨時點使用（橫斷面排序、回測）一律只准經過`known_at`或`align_to_daily`**，
    不得直接用`period_end`當可得日。"""
    inc = _wide(income, _INCOME_TYPES)
    bal = _wide(balance, _BALANCE_TYPES)
    ocf = _decumulate_ocf(cash)
    frame = pd.concat([inc, bal, ocf.rename("ocf")], axis=1, sort=False).sort_index()
    frame.index.name = "period_end"
    for a in ATOM_NAMES:
        if a not in frame.columns:
            frame[a] = np.nan
    # 股數＝歸屬母公司淨利/EPS（加權平均股數）。EPS==0→NaN（無定義）；
    # EPS四捨五入到0.01，EPS絕對值很小時此估計雜訊大，屬已知限制。
    with np.errstate(divide="ignore", invalid="ignore"):
        shares = frame["net_income"] / frame["eps"]
    frame["shares"] = shares.where(frame["eps"] != 0, np.nan)
    frame = frame[list(ATOM_NAMES)]
    frame["pit_date"] = [statutory_pit_date(ix) for ix in frame.index]
    frame["pit_source"] = "assumed_statutory"
    return frame


def load_quarter_frame(stock_id: str) -> pd.DataFrame:
    """從FinMind（經`load_dev`，截在VAL_END、有本機快取）載入並建表。"""
    from finmind_client import load_dev  # 延遲import：單元測試不需要網路/快取
    start = "2010-01-01"
    return build_quarter_frame(
        load_dev("TaiwanStockFinancialStatements", stock_id, start),
        load_dev("TaiwanStockBalanceSheet", stock_id, start),
        load_dev("TaiwanStockCashFlowsStatement", stock_id, start),
    )


# =============================================================================
# PIT存取：唯一合法的跨時點入口
# =============================================================================

def known_at(frame: pd.DataFrame, asof) -> pd.DataFrame:
    """asof當天（含）已可得的季度列（pit_date<=asof）。"""
    return frame[frame["pit_date"] <= pd.Timestamp(asof)]


def align_to_daily(series: pd.Series, pit_dates: pd.Series, dates) -> pd.Series:
    """把季度序列攤到日頻：每個日期取「pit_date<=該日」的最新一季的值。
    第一個pit_date之前回NaN。`series`與`pit_dates`需有相同索引（period_end）。
    注意：值是依pit_date取「最新已公布」，pit_date遞增性由法定期限保證
    （Q4的3/31＜次年Q1的5/15），所以最新已公布＝期別最新者。"""
    left = pd.DataFrame({"date": pd.to_datetime(pd.Index(dates))}).sort_values("date")
    right = pd.DataFrame({"pit_date": pd.to_datetime(pit_dates.values), "v": series.values}) \
        .sort_values("pit_date")
    merged = pd.merge_asof(left, right, left_on="date", right_on="pit_date", direction="backward")
    return pd.Series(merged["v"].values, index=merged["date"].values, name=series.name)


# =============================================================================
# 算子（財報專用）：輸入為以period_end為索引的季度Series
# =============================================================================

def _check_n(n: int) -> None:
    if n not in ALLOWED_FIN_WINDOWS:
        raise ValueError(f"財報算子窗口n只准用{ALLOWED_FIN_WINDOWS}季，收到{n}")


def _lag(s: pd.Series, k: int) -> pd.Series:
    """依曆法季度鍵取k季前的值（缺季→NaN），回傳索引與s相同。"""
    by_key = {_quarter_key(ix): v for ix, v in s.items()}
    return pd.Series([by_key.get(_quarter_key(ix) - k, np.nan) for ix in s.index],
                     index=s.index, dtype=float, name=s.name)


def _growth(cur: pd.Series, base: pd.Series) -> pd.Series:
    """cur/base−1；base≤0（虧損/零）→NaN（成長率無意義）。"""
    with np.errstate(divide="ignore", invalid="ignore"):
        g = cur / base - 1.0
    return g.where(base > 0, np.nan)


def fin_yoy(s: pd.Series) -> pd.Series:
    """年增率：s/去年同季−1。基期≤0→NaN。"""
    return _growth(s, _lag(s, 4))


def fin_qoq(s: pd.Series) -> pd.Series:
    """季增率：s/上一季−1。基期≤0→NaN。上一季缺（不連續）→NaN。
    **季節性提醒**：台股營收/EPS有強季節性，qoq常被季節污染，優先用yoy。"""
    return _growth(s, _lag(s, 1))


def fin_ttm(s: pd.Series) -> pd.Series:
    """近四季合計；**四季必須曆法連續且皆非NaN**，否則NaN。
    只適用流量科目（時點科目相加無意義→ValueError）。"""
    if s.name in STOCK_ATOMS:
        raise ValueError(f"{s.name}是時點值，ttm加總無意義")
    return sum(_lag(s, k) for k in range(4)) if len(s) else s.astype(float)


def fin_slope(s: pd.Series, n: int) -> pd.Series:
    """最近n季（含當季）對時間的OLS斜率（單位＝s的單位/季）。n∈{4,8}；
    n=1無法定義斜率→ValueError。窗內任一季缺或NaN→NaN。"""
    _check_n(n)
    if n < 2:
        raise ValueError("slope至少需要2個點，n=1無定義")
    x = np.arange(n, dtype=float)
    xc = x - x.mean()
    lags = [_lag(s, n - 1 - i) for i in range(n)]  # 由舊到新
    mat = np.column_stack([l.values for l in lags])
    ok = ~np.isnan(mat).any(axis=1)
    out = np.full(len(s), np.nan)
    out[ok] = (mat[ok] * xc).sum(axis=1) / (xc ** 2).sum()
    return pd.Series(out, index=s.index, name=s.name)


def fin_delta_yoy(s: pd.Series) -> pd.Series:
    """成長加速度：本季yoy − 上一季yoy。任一季yoy是NaN→NaN。"""
    y = fin_yoy(s)
    return y - _lag(y, 1)


def expected_seasonal_naive(s: pd.Series) -> pd.Series:
    """預期＝去年同季值（零參數的季節性隨機漫步）。"""
    return _lag(s, 4)


def expected_seasonal_drift(s: pd.Series) -> pd.Series:
    """預期＝去年同季值＋上一季相對其去年同季的年增量（SUE慣用預期，零參數）。
    E_t = s_{t-4} + (s_{t-1} − s_{t-5})。"""
    return _lag(s, 4) + (_lag(s, 1) - _lag(s, 5))


def fin_surprise(actual: pd.Series, expected: pd.Series) -> pd.Series:
    """標準化意外：(實際−預期)/ts_std(意外, 8季)。
    意外序列的標準差取**含當季的最近8個曆法連續季**，8季需齊全且非NaN，
    std==0→NaN。沒有分析師預期資料，`expected`由呼叫端提供
    （建議用上面兩個零參數的預期函式）。"""
    sur = actual - expected
    lags = np.column_stack([_lag(sur, k).values for k in range(8)])
    ok = ~np.isnan(lags).any(axis=1)
    sd = np.full(len(sur), np.nan)
    sd[ok] = lags[ok].std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = sur.values / sd
    z = np.where(sd > 0, z, np.nan)
    return pd.Series(z, index=sur.index, name=actual.name)


def fin_ratio(x: pd.Series, y: pd.Series) -> pd.Series:
    """佔比x/y；**y≤0→NaN**（負權益/零分母的比率無經濟意義，硬算會製造假訊號）。"""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = x / y
    return r.where(y > 0, np.nan)


FIN_OPERATORS = {
    "yoy": fin_yoy, "qoq": fin_qoq, "ttm": fin_ttm, "slope": fin_slope,
    "delta_yoy": fin_delta_yoy, "surprise": fin_surprise, "ratio": fin_ratio,
}


# =============================================================================
# 單元測試（合成資料，不連網）
# =============================================================================

def _long(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "type", "value"])


def _qs(vals: list, start: str = "2020-03-31", name: str = "revenue") -> pd.Series:
    idx = pd.date_range(start, periods=len(vals), freq="QE")
    return pd.Series(vals, index=idx, dtype=float, name=name)


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            failures.append(name)

    def close(a, b, tol=1e-9) -> bool:
        return pd.notna(a) and abs(a - b) < tol

    # ---- PIT ----
    check("PIT.Q1=5/15", statutory_pit_date("2024-03-31") == pd.Timestamp("2024-05-15"))
    check("PIT.Q2=8/14", statutory_pit_date("2024-06-30") == pd.Timestamp("2024-08-14"))
    check("PIT.Q3=11/14", statutory_pit_date("2024-09-30") == pd.Timestamp("2024-11-14"))
    check("PIT.Q4=次年3/31（非期末+45日的2/14）",
          statutory_pit_date("2024-12-31") == pd.Timestamp("2025-03-31"))
    check("PIT.2012年Q4取保守4/30", statutory_pit_date("2012-12-31") == pd.Timestamp("2013-04-30"))
    check("PIT.2012年Q2取保守8/31", statutory_pit_date("2012-06-30") == pd.Timestamp("2012-08-31"))
    check("PIT.Q4晚於期末+45日（pit.py前視缺陷的證據）",
          statutory_pit_date("2024-12-31") > pd.Timestamp("2024-12-31") + pd.Timedelta(days=45))
    pits = [statutory_pit_date(d) for d in pd.date_range("2013-03-31", periods=40, freq="QE")]
    check("PIT.遞增性（align_to_daily的前提）", all(a < b for a, b in zip(pits, pits[1:])))

    # ---- 建表：11個原子 ----
    inc = _long([
        ("2023-12-31", "Revenue", 1000), ("2023-12-31", "EPS", 2.0), ("2023-12-31", "GrossProfit", 400),
        ("2023-12-31", "OperatingIncome", 200), ("2023-12-31", "EquityAttributableToOwnersOfParent", 180),
        ("2024-03-31", "Revenue", 1100), ("2024-03-31", "EPS", -0.5), ("2024-03-31", "GrossProfit", 0),
        ("2024-03-31", "OperatingIncome", -50), ("2024-03-31", "EquityAttributableToOwnersOfParent", -45),
    ])
    bal = _long([
        ("2023-12-31", "TotalAssets", 5000), ("2023-12-31", "EquityAttributableToOwnersOfParent", 3000),
        ("2023-12-31", "Inventories", 300), ("2023-12-31", "AccountsReceivableNet", 250),
        ("2024-03-31", "TotalAssets", 5200), ("2024-03-31", "EquityAttributableToOwnersOfParent", -10),
        ("2024-03-31", "Inventories", 320),
    ])
    cash = _long([
        ("2023-03-31", "CashFlowsFromOperatingActivities", 100),
        ("2023-06-30", "CashFlowsFromOperatingActivities", 250),
        ("2023-09-30", "CashFlowsFromOperatingActivities", 330),
        ("2023-12-31", "CashFlowsFromOperatingActivities", 500),
        ("2024-03-31", "CashFlowsFromOperatingActivities", 90),
    ])
    f = build_quarter_frame(inc, bal, cash)
    check("frame含11個原子", all(a in f.columns for a in ATOM_NAMES) and len(ATOM_NAMES) == 11)
    q4 = f.loc["2023-12-31"]
    q1 = f.loc["2024-03-31"]
    check("atom.revenue", q4["revenue"] == 1000)
    check("atom.eps", q4["eps"] == 2.0)
    check("atom.gross_profit", q4["gross_profit"] == 400)
    check("atom.op_income", q4["op_income"] == 200)
    check("atom.net_income取損益表同名type（非權益）", q4["net_income"] == 180 and q4["equity"] == 3000)
    check("atom.total_assets", q4["total_assets"] == 5000)
    check("atom.equity", q4["equity"] == 3000)
    check("atom.inventory", q4["inventory"] == 300)
    check("atom.receivable", q4["receivable"] == 250)
    check("atom.ocf.Q4=全年累計−Q3累計", q4["ocf"] == 500 - 330)
    check("atom.ocf.Q1=累計值本身", q1["ocf"] == 90)
    check("atom.shares=淨利/EPS", close(q4["shares"], 90.0))
    check("atom.shares.虧損時淨利與EPS同號→正股數", close(q1["shares"], 90.0))
    check("負值：虧損季原子照實保留（不被清成0/NaN）", q1["op_income"] == -50 and q1["eps"] == -0.5)
    check("缺值：缺科目→NaN不是0", pd.isna(q1["receivable"]))
    check("pit_date欄位存在且＝法定期限", q4["pit_date"] == pd.Timestamp("2024-03-31"))
    check("pit_source標assumed_statutory", (f["pit_source"] == "assumed_statutory").all())

    # ---- 分母為零：EPS=0 → shares NaN ----
    z = build_quarter_frame(_long([("2024-03-31", "EPS", 0.0),
                                   ("2024-03-31", "EquityAttributableToOwnersOfParent", 0.0)]), None, None)
    check("shares.EPS=0→NaN", pd.isna(z["shares"].iloc[0]))

    # ---- 財報重編：重複列取最後一列，且確定性 ----
    dup = _long([("2024-03-31", "Revenue", 100), ("2024-03-31", "Revenue", 120)])
    fd = build_quarter_frame(dup, None, None)
    check("重編：重複(期別,科目)取最後一列", fd["revenue"].iloc[0] == 120)
    check("重編：只留一列不重複", len(fd) == 1)

    # ---- 空輸入 ----
    fe = build_quarter_frame(None, None, None)
    check("空輸入回空表且欄位齊全", len(fe) == 0 and all(a in fe.columns for a in ATOM_NAMES))

    # ---- ocf季度不連續：Q3累計缺→Q4單季NaN（不用Q2硬湊）----
    gap = build_quarter_frame(None, None, _long([
        ("2023-06-30", "CashFlowsFromOperatingActivities", 250),
        ("2023-12-31", "CashFlowsFromOperatingActivities", 500)]))
    check("ocf不連續：缺上一季累計→NaN", pd.isna(gap.loc["2023-12-31", "ocf"]))
    # ocf退回備援type
    alt = build_quarter_frame(None, None, _long([
        ("2024-03-31", "NetCashInflowFromOperatingActivities", 77)]))
    check("ocf備援type", alt["ocf"].iloc[0] == 77)

    # ---- 算子：yoy ----
    s = _qs([100, 110, 120, 130, 150, 99, 0, 140, -20])   # 2020Q1..2022Q1
    y = fin_yoy(s)
    check("yoy.正常", close(y.iloc[4], 0.5))
    check("yoy.前4季無去年同季→NaN", y.iloc[:4].isna().all())
    check("yoy.衰退為負", close(y.iloc[5], 99 / 110 - 1))
    check("yoy.當季值為0（基期正）＝−100%", close(fin_yoy(_qs([5, 5, 5, 5, 0])).iloc[4], -1.0))
    base0 = _qs([0, 5, 5, 5, 8])
    check("yoy.基期為0→NaN", pd.isna(fin_yoy(base0).iloc[4]))
    neg_base = _qs([-10, 5, 5, 5, 8])
    check("yoy.基期為負（虧損）→NaN", pd.isna(fin_yoy(neg_base).iloc[4]))
    check("yoy.當季轉虧（基期正）仍可算", close(fin_yoy(_qs([10, 1, 1, 1, -5])).iloc[4], -1.5))
    sk = _qs([100, 110, 120, 130, 150, 160]).drop(pd.Timestamp("2020-06-30"))
    check("yoy.季度不連續：去年同季缺→NaN（不誤用不相鄰季）", pd.isna(fin_yoy(sk).loc["2021-06-30"]))
    check("yoy.NaN傳播", pd.isna(fin_yoy(_qs([1, 1, 1, 1, np.nan])).iloc[4]))

    # ---- qoq ----
    q = fin_qoq(_qs([100, 110, 0, 50, -5]))
    check("qoq.正常", close(q.iloc[1], 0.1))
    check("qoq.首筆NaN", pd.isna(q.iloc[0]))
    check("qoq.基期為0→NaN", pd.isna(q.iloc[3]))
    check("qoq.基期為負→NaN(實測)", pd.isna(fin_qoq(_qs([-5, 3])).iloc[1]))
    check("qoq.季度不連續→NaN", pd.isna(fin_qoq(_qs([1, 2, 3, 4]).drop(pd.Timestamp("2020-06-30"))).loc["2020-09-30"]))

    # ---- ttm ----
    t = fin_ttm(_qs([1, 2, 3, 4, 5]))
    check("ttm.正常", t.iloc[3] == 10 and t.iloc[4] == 14)
    check("ttm.前3季NaN", t.iloc[:3].isna().all())
    check("ttm.含NaN→NaN", pd.isna(fin_ttm(_qs([1, np.nan, 3, 4, 5])).iloc[4]))
    check("ttm.含虧損季照實加總", fin_ttm(_qs([5, -8, 3, 4])).iloc[3] == 4)
    check("ttm.季度不連續→NaN", pd.isna(fin_ttm(_qs([1, 2, 3, 4, 5]).drop(pd.Timestamp("2020-06-30"))).iloc[-1]))
    try:
        fin_ttm(_qs([1, 2, 3, 4], name="total_assets"))
        check("ttm.時點科目應ValueError", False)
    except ValueError:
        check("ttm.時點科目應ValueError", True)

    # ---- slope ----
    sl = fin_slope(_qs([10, 20, 30, 40, 50]), 4)
    check("slope.線性序列=10/季", close(sl.iloc[3], 10.0) and close(sl.iloc[4], 10.0))
    check("slope.窗不足→NaN", sl.iloc[:3].isna().all())
    check("slope.含NaN→NaN", pd.isna(fin_slope(_qs([10, np.nan, 30, 40, 50]), 4).iloc[4]))
    check("slope.常數序列=0", close(fin_slope(_qs([7] * 8), 8).iloc[7], 0.0))
    check("slope.季度不連續→NaN", pd.isna(fin_slope(_qs([1, 2, 3, 4, 5]).drop(pd.Timestamp("2020-06-30")), 4).iloc[-1]))
    for bad in (1, 2, 3, 5, 20):
        try:
            fin_slope(_qs([1] * 10), bad)
            check(f"slope.n={bad}應ValueError", False)
        except ValueError:
            check(f"slope.n={bad}應ValueError", True)

    # ---- delta_yoy ----
    dy = fin_delta_yoy(_qs([100, 100, 100, 100, 110, 130]))
    check("delta_yoy.正常", close(dy.iloc[5], 0.3 - 0.1))
    check("delta_yoy.需兩個yoy→前5筆NaN", dy.iloc[:5].isna().all())
    check("delta_yoy.基期虧損→NaN", pd.isna(fin_delta_yoy(_qs([-1, 100, 100, 100, 110, 130])).iloc[5]))

    # ---- 預期 ----
    e1 = expected_seasonal_naive(_qs([1, 2, 3, 4, 5]))
    check("expected_naive", e1.iloc[4] == 1 and e1.iloc[:4].isna().all())
    e2 = expected_seasonal_drift(_qs([10, 20, 30, 40, 12, 26]))
    check("expected_drift", close(e2.iloc[5], 20 + (12 - 10)))
    check("expected_drift.前5筆NaN", e2.iloc[:5].isna().all())

    # ---- surprise ----
    act = _qs([10, 12, 9, 15, 11, 14, 10, 16, 13, 18, 12, 17], name="eps")
    exp = expected_seasonal_naive(act)
    sp = fin_surprise(act, exp)
    check("surprise.前面不足8季意外→NaN", sp.iloc[:11].isna().all())
    sur = (act - exp).iloc[4:12].values
    check("surprise.正常值", close(sp.iloc[11], sur[-1] / np.std(sur, ddof=1), 1e-9))
    flat = _qs([1] * 8, name="eps")
    check("surprise.std為0→NaN", fin_surprise(flat, flat * 0).isna().all())
    check("surprise.意外含NaN→NaN", pd.isna(fin_surprise(act.copy().where(act.index != act.index[8]), exp).iloc[11]))
    check("surprise.只用過去（改動未來值不影響過去）",
          close(fin_surprise(act.iloc[:12], exp.iloc[:12]).iloc[11],
                fin_surprise(pd.concat([act, _qs([999], start="2023-03-31")]),
                             expected_seasonal_naive(pd.concat([act, _qs([999], start="2023-03-31")]))).iloc[11]))

    # ---- ratio ----
    r = fin_ratio(_qs([40, 50, 10, 5, np.nan]), _qs([100, 0, -20, 50, 10]))
    check("ratio.正常", close(r.iloc[0], 0.4))
    check("ratio.分母為零→NaN", pd.isna(r.iloc[1]))
    check("ratio.分母為負→NaN", pd.isna(r.iloc[2]))
    check("ratio.分子NaN→NaN", pd.isna(r.iloc[4]))
    check("ratio.分子為負（虧損）照實保留", close(fin_ratio(_qs([-5]), _qs([50])).iloc[0], -0.1))

    # ---- 窗口強制 ----
    check("ALLOWED_FIN_WINDOWS={1,4,8}", ALLOWED_FIN_WINDOWS == (1, 4, 8))
    try:
        _check_n(20)
        check("窗口20應ValueError", False)
    except ValueError:
        check("窗口20應ValueError", True)

    # ---- PIT對齊：known_at / align_to_daily ----
    check("known_at.Q4在3/30不可得", "2023-12-31" not in
          [str(i.date()) for i in known_at(f, "2024-03-30").index])
    check("known_at.Q4在3/31可得", pd.Timestamp("2023-12-31") in known_at(f, "2024-03-31").index)
    check("known_at.Q1(3/31期別)在4/15不可得（期別日≠可得日）",
          pd.Timestamp("2024-03-31") not in known_at(f, "2024-04-15").index)
    daily = align_to_daily(f["revenue"], f["pit_date"], ["2024-03-30", "2024-03-31", "2024-05-14", "2024-05-15"])
    check("align.首個pit_date前→NaN", pd.isna(daily.iloc[0]))
    check("align.3/31起看到Q4=1000", daily.iloc[1] == 1000)
    check("align.5/14仍是Q4", daily.iloc[2] == 1000)
    check("align.5/15起換成Q1=1100", daily.iloc[3] == 1100)
    dq = align_to_daily(fin_yoy(_qs([100, 100, 100, 100, 150])), pd.Series(
        [statutory_pit_date(i) for i in _qs([1] * 5).index], index=_qs([1] * 5).index), ["2021-05-14", "2021-05-15"])
    check("align.算子先在季度層算完再對齊（yoy在2021Q1的pit_date前不可見）",
          pd.isna(dq.iloc[0]))
    check("align.yoy在pit_date當天起可見", close(dq.iloc[1], 0.5))

    check("FIN_OPERATORS含7個算子", len(FIN_OPERATORS) == 7)

    if failures:
        print(f"[FAIL] {len(failures)}項未過：{failures}")
        return 1
    print(f"[PASS] FIN_ATOM_LIBRARY.py 自我測試全部通過（{len(ATOM_NAMES)}個原子、"
          f"{len(FIN_OPERATORS)}個算子＋2個預期函式，含缺值/負值/分母為零/重編/季度不連續/PIT情境）")
    return 0


def real_data_smoke() -> int:
    """2330真實資料煙霧測試（讀本機快取，經load_dev，不越過VAL_END）。"""
    f = load_quarter_frame("2330")
    ok = True
    print(f"2330季度列數={len(f)}，期別{f.index.min().date()}~{f.index.max().date()}")
    if f.index.max() > pd.Timestamp("2024-12-31"):
        print("[FAIL] 出現VAL_END之後的期別（HOLDOUT洩漏）")
        ok = False
    print(f.tail(5)[["revenue", "eps", "net_income", "ocf", "shares", "pit_date"]].to_string())
    q = f.loc["2023-12-31"]
    # 已知：2330 2023全年EPS約32.34、Q4單季營收約6,255億（±以快取值為準，僅做量級檢查）
    if not (5e11 < q["revenue"] < 8e11):
        print(f"[FAIL] 2023Q4營收量級異常：{q['revenue']}")
        ok = False
    ocf_sum = f.loc["2023-03-31":"2023-12-31", "ocf"].sum()
    print(f"2023四季單季OCF加總={ocf_sum:.4g}（應等於2023全年累計1.242e12）")
    if not abs(ocf_sum - 1.241967e12) / 1.241967e12 < 1e-6:
        print("[FAIL] OCF還原單季後加總≠全年累計")
        ok = False
    y = fin_yoy(f["revenue"])
    print(f"2023Q4營收yoy={y.loc['2023-12-31']:.4f}")
    print("[PASS] 真實資料煙霧測試" if ok else "[FAIL] 真實資料煙霧測試")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv or "--real-data" in sys.argv:
        rc = self_test() if "--self-test" in sys.argv else 0
        if "--real-data" in sys.argv:
            rc = rc or real_data_smoke()
        sys.exit(rc)
    print(__doc__)
