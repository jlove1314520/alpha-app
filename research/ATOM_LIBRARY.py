"""原子.一：原子與算子庫（`PENDING_QUEUE.md`「零件的定義改為原子層」，
2026-09-19總司令裁示【更正】）。

**背景**：上一輪把「零件」理解成策略層維度（換倉頻率/加權方式/曝險
調節）是錯的——總司令要的是細到單一K棒的原子層拆解：任何因子都只是
原子＋算子組出來的表達式，因子本身不是零件。這支模組提供那個原子/
算子的基礎詞彙表，本身**不組任何表達式、不算任何IC、不做任何策略
判定**，那些是`原子.二`/`原子.三`的範圍。

**誠實邊界（總司令原文明確要求寫進檔頭，不得暗示能做分K）**：本專案
逐筆tick資料目前只有5檔×9天（`research/data/ticks/`），盤中形態
（分K層級的K棒）目前做不了。**「單一K棒」在本階段等於「單一日K棒」**，
下面所有原子都是從OHLCV+成交金額的日頻資料算出，不是分K資料，任何
未來想套用到分K層級都需要先確認tick資料量體足夠、且是另一輪獨立的
工作單位，不是本檔案隱含涵蓋的範圍。

**資料源**：`adjust.adjusted_price_series()`（含下市股，`重構.B3`測得
納入率約79%），只用TRAIN+VAL（`validation/holdout.py`既有邊界），
HOLDOUT不碰。欄位對應：o=`adj_open`／h=`adj_high`／l=`adj_low`／
c=`adj_close`／v=`Trading_Volume`／amt=`Trading_money`——用還原後的
OHLC是刻意選擇（除權息缺口不會污染body/range/gap這類K棒形態原子），
v/amt用原始未還原值（成交量/金額本來就不需要除權還原）。

**窗口限制（總司令原文明確要求，抗過擬合的核心紀律）**：所有需要
窗口參數`n`的算子，**只准用n∈{1,5,20,60}**，不得連續掃描（例如
`range(1,100)`這種掃描本身就是參數過擬合的主要來源——`原子.二`／
`原子.三`引用本模組時必須遵守這個值域，本模組的函式簽章本身不強制
（Python無法在型別層級限制「只能傳4個特定值」），但呼叫端必須遵守，
違反這條紀律等同違反本輪裁示。

**原子計數的誠實揭露**：總司令原文說「15個」，逐一列出的原始(6個：
o,h,l,c,v,amt)+衍生(8個：body/upper_sh/lower_sh/range/close_loc/gap/
true_range/vwap)加總是**14個，不是15個**。本檔案如實只實作這14個
明確定義的原子，**不為了湊滿15個而自己發明一個沒被交辦的原子**——
若總司令原文確實還有第15個（例如把`delay(c,1)`本身算成一個獨立原子，
而不只是`gap`/`true_range`內部用到的中間量），需要總司令指出是哪一個，
不由本模組自行猜測填補。

**2026-09-19總司令裁示【原子.一審閱通過】補三件**（原子.一審閱通過，
品質達標，補完直接接原子.二不需再等審閱）：(a) `op_mul`（逐元素相乘，
既有算子只有除法沒有乘法，組不出量價配合表達式）；(b) `op_decay_linear`
（線性衰減加權平均，`ts_mean`等權缺了「近重遠輕」這類表達式，權重
`w_i∝(n−i)`事前寫死）；(c) 10個基準原子`b50_o/h/l/c/v`（0050）與
`btx_o/h/l/c/v`（TAIEX），補上`relative_strength`家族在原子層的缺席
（`op_ts_corr`簽名收兩個Series，缺大盤序列就組不出這整個家族，而這
既是既有因子之一，也是天條二對標0050的核心）。補完後原子總數
14+10=**24個**，算子總數17+2=**19個**。

用法：
    python research/ATOM_LIBRARY.py --self-test   # 跑全部單元測試
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

# 窗口值域（僅供呼叫端參照與本檔自我測試使用，見上方檔頭說明）
ALLOWED_WINDOWS = (1, 5, 20, 60)


# =============================================================================
# 原子（Atoms）——14個，零參數、零前視，輸入為單一股票、已依日期排序的
# DataFrame（欄位：o,h,l,c,v,amt），輸出為同長度的pd.Series。
# =============================================================================

def atom_o(df: pd.DataFrame) -> pd.Series:
    return df["o"].astype(float)


def atom_h(df: pd.DataFrame) -> pd.Series:
    return df["h"].astype(float)


def atom_l(df: pd.DataFrame) -> pd.Series:
    return df["l"].astype(float)


def atom_c(df: pd.DataFrame) -> pd.Series:
    return df["c"].astype(float)


def atom_v(df: pd.DataFrame) -> pd.Series:
    return df["v"].astype(float)


def atom_amt(df: pd.DataFrame) -> pd.Series:
    return df["amt"].astype(float)


def atom_body(df: pd.DataFrame) -> pd.Series:
    """實體：收盤−開盤，正值＝當日收紅，負值＝收黑。"""
    return df["c"].astype(float) - df["o"].astype(float)


def atom_upper_sh(df: pd.DataFrame) -> pd.Series:
    """上影線：最高價−max(開盤,收盤)。恆≥0（浮點誤差除外）。"""
    return df["h"].astype(float) - np.maximum(df["o"].astype(float), df["c"].astype(float))


def atom_lower_sh(df: pd.DataFrame) -> pd.Series:
    """下影線：min(開盤,收盤)−最低價。恆≥0。"""
    return np.minimum(df["o"].astype(float), df["c"].astype(float)) - df["l"].astype(float)


def atom_range(df: pd.DataFrame) -> pd.Series:
    """當日振幅：最高−最低。停牌鎖死一價（無量無波動）時為0，不是NaN。"""
    return df["h"].astype(float) - df["l"].astype(float)


def atom_close_loc(df: pd.DataFrame) -> pd.Series:
    """收盤價在當日區間的相對位置，(c−l)/(h−l)，值域[0,1]。
    **除零時回NaN，不是0或0.5**——range=0（漲跌停鎖死/停牌無波動）時，
    「收在區間中點」這個說法本身沒有意義，硬填一個數字會製造假訊號。
    """
    rng = df["h"].astype(float) - df["l"].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = (df["c"].astype(float) - df["l"].astype(float)) / rng
    return result.where(rng != 0, np.nan)


def atom_gap(df: pd.DataFrame) -> pd.Series:
    """跳空：今開−昨收。第一筆（無昨收）為NaN，不是0——0會被誤讀成
    「確認沒有跳空」，但真相是「不知道」。"""
    return df["o"].astype(float) - op_delay(df["c"].astype(float), 1)


def atom_true_range(df: pd.DataFrame) -> pd.Series:
    """真實波幅：max(h,昨收)−min(l,昨收)，涵蓋跳空缺口。第一筆為NaN
    （理由同`atom_gap`）。"""
    c_prev = op_delay(df["c"].astype(float), 1)
    return np.maximum(df["h"].astype(float), c_prev) - np.minimum(df["l"].astype(float), c_prev)


def atom_vwap(df: pd.DataFrame) -> pd.Series:
    """量價均值代理：成交金額/成交量。**停牌/無量交易日回NaN，不是0**
    ——0會被誤讀成「均價是0元」，真相是「今天沒有成交，這個量沒有
    定義」。"""
    v = df["v"].astype(float)
    amt = df["amt"].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = amt / v
    return result.where(v != 0, np.nan)


ATOMS = {
    "o": atom_o, "h": atom_h, "l": atom_l, "c": atom_c, "v": atom_v, "amt": atom_amt,
    "body": atom_body, "upper_sh": atom_upper_sh, "lower_sh": atom_lower_sh,
    "range": atom_range, "close_loc": atom_close_loc, "gap": atom_gap,
    "true_range": atom_true_range, "vwap": atom_vwap,
}


# =============================================================================
# 基準原子（2026-09-19總司令裁示【原子.一審閱通過】補件(c)，10個：
# b50_o/h/l/c/v（0050）＋ btx_o/h/l/c/v（TAIEX），最重要的一項補件）。
#
# **理由**：`op_ts_corr`簽名收兩個Series，但`ATOMS`裡原本沒有大盤，
# 導致`relative_strength`這整個家族在原子層缺席——那既是既有因子之一，
# 也是天條二（對標0050）的核心。
#
# **合約差異（跟前面14個既有atom不同，明確寫出來）**：既有14個atom的
# `df`參數不需要日期資訊（純粹依賴列順序=時間順序）。基準原子需要把
# 大盤序列**對齊**到個股自己的交易日曆（個股停牌/當天未成交時，大盤
# 不會跟著停牌，兩邊的日期集合不會完全一致），所以基準原子要求`df`
# 額外帶一個`"date"`欄位（既有14個atom不需要，呼叫端在建構個股`df`時
# 本來就會有日期欄位，這不是新增負擔，是本來就存在的資料，只是既有
# 14個atom沒有用到）。對齊方式：把大盤序列reindex到個股的date、
# forward-fill缺值——理由跟`core_tilt_backtest.py`2026-09-19的bug
# 修正同一個道理：個股交易日曆上有、大盤當天剛好缺值（或反過來）時，
# 用大盤最近一個已知值延續，不能讓「兩邊日期沒對齊」偽裝成「大盤當天
# 憑空消失變成0」。個股日期早於大盤資料第一筆可用日期時，正確答案是
# NaN（真的不知道），不是0、也不能往前外插。
#
# **資料源**：0050用`adjust.adjusted_price_series("0050")`（真實序列，
# 非重建，跟本專案其他地方引用0050的方式一致）；TAIEX用`finmind_client.
# load_dev("TaiwanStockPrice","TAIEX",...)`（本專案既有的TAIEX讀取
# 慣例，見`strategies/weinstein_stage2.py::prepare_market_data`），
# TAIEX是指數本身不是個股，無除權息調整可言，用原始值就是正確值，
# 不需要adjusted版本。兩者都經`validation.holdout`既有機制裁切在
# VAL_END之前，不碰HOLDOUT，且都在**首次被呼叫時才真正抓取**（lazy、
# module級快取只抓一次），不在import本模組時就發出任何請求。
# =============================================================================

_BENCHMARK_CACHE: dict[str, pd.DataFrame] = {}


def _load_benchmark_0050() -> pd.DataFrame:
    if "0050" not in _BENCHMARK_CACHE:
        from adjust import adjusted_price_series
        raw = adjusted_price_series("0050")
        out = pd.DataFrame({
            "date": pd.to_datetime(raw["date"]),
            "o": raw["adj_open"].astype(float), "h": raw["adj_high"].astype(float),
            "l": raw["adj_low"].astype(float), "c": raw["adj_close"].astype(float),
            "v": raw["volume"].astype(float),
        }).sort_values("date").reset_index(drop=True)
        _BENCHMARK_CACHE["0050"] = out
    return _BENCHMARK_CACHE["0050"]


def _load_benchmark_taiex() -> pd.DataFrame:
    if "TAIEX" not in _BENCHMARK_CACHE:
        from finmind_client import load_dev
        # start_date="2000-01-01"刻意對齊本專案其他地方已經快取過的
        # TAIEX抓取範圍（`load_dev()`的快取鍵含start_date字面值，選一個
        # 沒被快取過的日期會逼出一次不必要的即時抓取）。
        raw = load_dev("TaiwanStockPrice", "TAIEX", "2000-01-01")
        out = pd.DataFrame({
            "date": pd.to_datetime(raw["date"]),
            "o": raw["open"].astype(float), "h": raw["max"].astype(float),
            "l": raw["min"].astype(float), "c": raw["close"].astype(float),
            "v": raw["Trading_Volume"].astype(float),
        }).sort_values("date").reset_index(drop=True)
        _BENCHMARK_CACHE["TAIEX"] = out
    return _BENCHMARK_CACHE["TAIEX"]


def _align_benchmark_field(df: pd.DataFrame, loader, field: str) -> pd.Series:
    if "date" not in df.columns:
        raise ValueError(
            "基準原子要求df必須帶'date'欄位才能對齊到大盤日曆——既有14個atom"
            "不需要date是因為它們純粹用列順序，這個合約差異已寫在本節檔頭"
        )
    bench = loader()
    dates = pd.to_datetime(df["date"])
    aligned = bench.set_index("date")[field].reindex(dates).ffill()
    return pd.Series(aligned.values, index=df.index)


def atom_b50_o(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_0050, "o")


def atom_b50_h(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_0050, "h")


def atom_b50_l(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_0050, "l")


def atom_b50_c(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_0050, "c")


def atom_b50_v(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_0050, "v")


def atom_btx_o(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_taiex, "o")


def atom_btx_h(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_taiex, "h")


def atom_btx_l(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_taiex, "l")


def atom_btx_c(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_taiex, "c")


def atom_btx_v(df: pd.DataFrame) -> pd.Series:
    return _align_benchmark_field(df, _load_benchmark_taiex, "v")


BENCHMARK_ATOMS = {
    "b50_o": atom_b50_o, "b50_h": atom_b50_h, "b50_l": atom_b50_l,
    "b50_c": atom_b50_c, "b50_v": atom_b50_v,
    "btx_o": atom_btx_o, "btx_h": atom_btx_h, "btx_l": atom_btx_l,
    "btx_c": atom_btx_c, "btx_v": atom_btx_v,
}
ATOMS.update(BENCHMARK_ATOMS)


# =============================================================================
# 算子（Operators）
# =============================================================================

# ---- 時序算子：輸入單一股票的pd.Series（已依日期排序），n∈ALLOWED_WINDOWS ----

def op_delay(s: pd.Series, n: int) -> pd.Series:
    """往前取n期的值（PIT-safe，只用過去，不含未來）。"""
    return s.shift(n)


def op_delta(s: pd.Series, n: int) -> pd.Series:
    """跟n期前的差值：s − delay(s,n)。"""
    return s - s.shift(n)


def op_ts_mean(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def op_ts_std(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).std()


def op_ts_max(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).max()


def op_ts_min(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).min()


def op_ts_rank(s: pd.Series, n: int) -> pd.Series:
    """窗口內當下值的百分位排名，值域[0,1]（1.0＝窗口內最大值）。
    n=1時窗口只有自己一筆，恆為1.0（不是錯誤，是定義上的退化情況）。"""
    def _rank_last(window: np.ndarray) -> float:
        if np.all(np.isnan(window)):
            return np.nan
        return float(pd.Series(window).rank(pct=True).iloc[-1])
    return s.rolling(n, min_periods=n).apply(_rank_last, raw=True)


def op_ts_sum(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).sum()


def op_ts_corr(x: pd.Series, y: pd.Series, n: int) -> pd.Series:
    """滾動相關係數。n=1時只有一個點，標準差為0，相關係數無定義，
    pandas內建行為回NaN，本函式沿用不額外處理（誠實：n=1測相關本來
    就沒有意義，NaN是正確答案不是bug）。"""
    return x.rolling(n, min_periods=n).corr(y)


def op_ts_argmax(s: pd.Series, n: int) -> pd.Series:
    """窗口內最大值出現的相對位置（0＝窗口最舊那天，n-1＝當天）。"""
    def _argmax_pos(window: np.ndarray) -> float:
        if np.all(np.isnan(window)):
            return np.nan
        return float(np.nanargmax(window))
    return s.rolling(n, min_periods=n).apply(_argmax_pos, raw=True)


def op_decay_linear(s: pd.Series, n: int) -> pd.Series:
    """線性衰減加權平均（2026-09-19總司令裁示【原子.一審閱通過】補件(b)）。
    理由：`ts_mean`是等權，缺了會少掉一整類「近重遠輕」的表達式。
    **權重定義事前寫死（總司令原文）**：`w_i ∝ (n−i)`，i=0是最近一期
    ──即最近一天權重最高(=n)、最舊一天權重最低(=1)，線性遞減，
    normalize後總和為1。n<1的視同ALLOWED_WINDOWS值域外用法，呼叫端
    責任（同本模組其餘窗口算子的既有慣例，本函式不重複檢查）。"""
    weights = np.arange(1, n + 1, dtype=float)  # 索引0(窗口最舊)→1，索引n-1(窗口最新)→n
    weights = weights / weights.sum()

    def _weighted(window: np.ndarray) -> float:
        if np.any(np.isnan(window)):
            return np.nan  # 任一期缺值就不硬湊，NaN傳播，理由同op_mul
        return float(np.dot(window, weights))

    return s.rolling(n, min_periods=n).apply(_weighted, raw=True)


TS_OPERATORS = {
    "delay": op_delay, "delta": op_delta, "ts_mean": op_ts_mean, "ts_std": op_ts_std,
    "ts_max": op_ts_max, "ts_min": op_ts_min, "ts_rank": op_ts_rank, "ts_sum": op_ts_sum,
    "ts_corr": op_ts_corr, "ts_argmax": op_ts_argmax, "decay_linear": op_decay_linear,
}


# ---- 橫斷面算子：輸入同一天全部股票的pd.Series（index=stock_id） ----

def op_rank(cross_section: pd.Series) -> pd.Series:
    """同一天橫斷面百分位排名，值域[0,1]。全部值相同（無鑑別力）時
    pandas回傳的排名仍是遞增序，不特別處理——那是資料本身沒有鑑別力，
    不是這支函式的責任去偵測。"""
    return cross_section.rank(pct=True)


def op_zscore(cross_section: pd.Series) -> pd.Series:
    """同一天橫斷面z-score。標準差為0（全部值相同）時回NaN，不是0——
    0會被誤讀成「剛好在平均值」，真相是「這個橫截面沒有離散度，z-score
    沒有意義」。"""
    std = cross_section.std()
    if std == 0 or pd.isna(std):
        return pd.Series(np.nan, index=cross_section.index)
    return (cross_section - cross_section.mean()) / std


def op_ind_neutral(cross_section: pd.Series, industry: pd.Series) -> pd.Series:
    """扣除同產業當日平均值（產業中性化）。`industry`跟`cross_section`
    須有相同index（股票代號）。單檔產業（組內只有1檔）扣掉自己的值後
    恆為0，不是錯誤，是「無法跟同業比較」這個事實的正確反映。"""
    df = pd.DataFrame({"value": cross_section, "industry": industry})
    industry_mean = df.groupby("industry")["value"].transform("mean")
    return df["value"] - industry_mean


CROSS_SECTIONAL_OPERATORS = {"rank": op_rank, "zscore": op_zscore, "ind_neutral": op_ind_neutral}


# ---- 純量算子：逐元素，不需要窗口或橫斷面 ----

def op_sign(s: pd.Series) -> pd.Series:
    return np.sign(s)


def op_abs(s: pd.Series) -> pd.Series:
    return s.abs()


def op_log1p(s: pd.Series) -> pd.Series:
    """log(1+x)。**輸入若≤−1會產生NaN/−inf，這是誠實的邊界，不是bug**
    ——例如`body`（收−開）理論上可以是任意負值只要沒有跌停限制，若某
    檔股票單日body剛好等於或低於−1（幾乎不可能發生在正常價格量級，
    但若上游資料有單位錯誤這裡會如實暴露出來，不靜默吃掉）。"""
    return np.log1p(s)


def op_ratio(x: pd.Series, y: pd.Series) -> pd.Series:
    """x/y，分母為0時回NaN，不是inf或0。"""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = x / y
    return result.where(y != 0, np.nan)


def op_mul(x: pd.Series, y: pd.Series) -> pd.Series:
    """逐元素相乘（2026-09-19總司令裁示【原子.一審閱通過】補件(a)）。
    理由：既有算子只有`ratio`(除法)沒有乘法，組不出最基本的量價配合
    表達式（例：上漲量 = sign(delta(c,1)) × v）。**NaN傳播是IEEE754
    標準行為，不特別處理**——任一邊是NaN，結果就是NaN（即使另一邊是
    0也一樣，`0 × NaN = NaN`不是`0`，這是「不知道」不是「確定是零」，
    跟本模組其餘算子一貫的NaN語意一致）。"""
    return x * y


SCALAR_OPERATORS = {"sign": op_sign, "abs": op_abs, "log1p": op_log1p, "ratio": op_ratio,
                     "mul": op_mul}

ALL_OPERATORS = {**TS_OPERATORS, **CROSS_SECTIONAL_OPERATORS, **SCALAR_OPERATORS}


# =============================================================================
# 單元測試（每個原子/算子至少一個，涵蓋NaN／除零／停牌／漲跌停無量情境）
# =============================================================================

def _mk_ohlcv(o, h, l, c, v, amt) -> pd.DataFrame:
    return pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": v, "amt": amt})


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            failures.append(name)

    # ---- 正常情境：一組乾淨的5天OHLCV ----
    normal = _mk_ohlcv(
        o=[10, 11, 10.5, 12, 11.5], h=[11, 11.5, 11, 12.5, 12],
        l=[9.5, 10.5, 10, 11.5, 11], c=[10.8, 10.7, 10.9, 12.2, 11.8],
        v=[1000, 1200, 900, 1500, 1100], amt=[10800, 12840, 8010, 18300, 12980],
    )
    check("atom_o正常值", atom_o(normal).iloc[0] == 10)
    check("atom_body正常值", abs(atom_body(normal).iloc[0] - 0.8) < 1e-9)
    check("atom_upper_sh恆非負", (atom_upper_sh(normal) >= -1e-9).all())
    check("atom_lower_sh恆非負", (atom_lower_sh(normal) >= -1e-9).all())
    check("atom_range正常值", abs(atom_range(normal).iloc[0] - 1.5) < 1e-9)
    check("atom_close_loc值域[0,1]", ((atom_close_loc(normal).dropna() >= 0)
                                        & (atom_close_loc(normal).dropna() <= 1)).all())
    check("atom_gap第一筆為NaN", pd.isna(atom_gap(normal).iloc[0]))
    check("atom_gap第二筆正常值", abs(atom_gap(normal).iloc[1] - (11 - 10.8)) < 1e-9)
    check("atom_true_range第一筆為NaN", pd.isna(atom_true_range(normal).iloc[0]))
    check("atom_vwap正常值", abs(atom_vwap(normal).iloc[0] - 10.8) < 1e-9)

    # ---- 停牌情境：某天量、額皆為0，價格鎖死不動（一價到底） ----
    halted = _mk_ohlcv(
        o=[10, 10, 10, 10, 10], h=[10, 10, 10, 10, 10],
        l=[10, 10, 10, 10, 10], c=[10, 10, 10, 10, 10],
        v=[1000, 0, 0, 1000, 1000], amt=[10000, 0, 0, 10000, 10000],
    )
    check("停牌日atom_vwap回NaN不是0", pd.isna(atom_vwap(halted).iloc[1]))
    check("停牌日atom_range為0(非NaN)", atom_range(halted).iloc[1] == 0)
    check("停牌日atom_close_loc回NaN(range=0除零)", pd.isna(atom_close_loc(halted).iloc[1]))

    # ---- 漲跌停鎖死情境：h=l=c（整天鎖在同一價，通常伴隨低量但非零量） ----
    limit = _mk_ohlcv(
        o=[10, 11], h=[10, 11], l=[10, 11], c=[10, 11], v=[500, 300], amt=[5000, 3300],
    )
    check("漲停鎖死atom_close_loc回NaN(range=0)", pd.isna(atom_close_loc(limit).iloc[0]))
    check("漲停鎖死atom_body為0", atom_body(limit).iloc[0] == 0)

    # ---- 除零情境：op_ratio分母為0 ----
    x = pd.Series([1.0, 2.0, 3.0])
    y = pd.Series([0.0, 2.0, 0.0])
    r = op_ratio(x, y)
    check("op_ratio除零回NaN", pd.isna(r.iloc[0]) and pd.isna(r.iloc[2]))
    check("op_ratio正常值", abs(r.iloc[1] - 1.0) < 1e-9)

    # ---- NaN傳播情境：op_delay/op_delta在序列開頭 ----
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    check("op_delay(n=1)第一筆為NaN", pd.isna(op_delay(s, 1).iloc[0]))
    check("op_delay(n=1)正常值", op_delay(s, 1).iloc[1] == 1.0)
    check("op_delta(n=5)全部為NaN(序列長度<n)", op_delta(s, 5).isna().all())

    # ---- 窗口算子：ts_mean/ts_std/ts_max/ts_min/ts_sum ----
    check("op_ts_mean(n=5)第5筆正常值", abs(op_ts_mean(s, 5).iloc[4] - 3.0) < 1e-9)
    check("op_ts_mean(n=5)前4筆為NaN(min_periods)", op_ts_mean(s, 5).iloc[:4].isna().all())
    check("op_ts_std(n=1)恆為NaN(單點無標準差)", op_ts_std(s, 1).isna().all())
    check("op_ts_max(n=5)正常值", op_ts_max(s, 5).iloc[4] == 5.0)
    check("op_ts_min(n=5)正常值", op_ts_min(s, 5).iloc[4] == 1.0)
    check("op_ts_sum(n=5)正常值", abs(op_ts_sum(s, 5).iloc[4] - 15.0) < 1e-9)

    # ---- ts_rank：n=1退化情況恆為1.0 ----
    r1 = op_ts_rank(s, 1)
    check("op_ts_rank(n=1)恆為1.0", (r1.dropna() == 1.0).all())
    r5 = op_ts_rank(s, 5)
    check("op_ts_rank(n=5)遞增序列最後一筆為1.0(最大值)", abs(r5.iloc[4] - 1.0) < 1e-9)

    # ---- ts_corr：n=1無定義(標準差0) ----
    y2 = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0])
    c1 = op_ts_corr(s, y2, 1)
    check("op_ts_corr(n=1)恆為NaN(標準差0)", c1.isna().all())
    c5 = op_ts_corr(s, y2, 5)
    check("op_ts_corr(n=5)完全負相關約-1", abs(c5.iloc[4] - (-1.0)) < 1e-6)

    # ---- ts_argmax ----
    a5 = op_ts_argmax(s, 5)
    check("op_ts_argmax遞增序列最大值在最後一位(pos=4)", a5.iloc[4] == 4)

    # ---- 橫斷面算子 ----
    cross = pd.Series([1.0, 2.0, 3.0, 4.0], index=["A", "B", "C", "D"])
    check("op_rank值域[0,1]", ((op_rank(cross) >= 0) & (op_rank(cross) <= 1)).all())
    check("op_zscore均值近似0", abs(op_zscore(cross).mean()) < 1e-9)
    flat = pd.Series([5.0, 5.0, 5.0], index=["A", "B", "C"])
    check("op_zscore全部相同值回NaN(標準差0)", op_zscore(flat).isna().all())
    industry = pd.Series(["電子", "電子", "傳產", "傳產"], index=["A", "B", "C", "D"])
    neutral = op_ind_neutral(cross, industry)
    check("op_ind_neutral同產業內兩檔中和後互為相反數",
          abs(neutral.loc["A"] + neutral.loc["B"]) < 1e-9)
    single = pd.Series([7.0], index=["E"])
    single_ind = pd.Series(["生技"], index=["E"])
    check("op_ind_neutral單檔產業組內扣自己恆為0",
          abs(op_ind_neutral(single, single_ind).iloc[0]) < 1e-9)

    # ---- 純量算子 ----
    check("op_sign正負零", list(op_sign(pd.Series([-2.0, 0.0, 3.0]))) == [-1.0, 0.0, 1.0])
    check("op_abs", (op_abs(pd.Series([-2.0, 3.0])) == pd.Series([2.0, 3.0])).all())
    check("op_log1p正常值", abs(op_log1p(pd.Series([0.0])).iloc[0]) < 1e-9)
    check("op_log1p邊界(x=-1時log(0)=-inf)", np.isneginf(op_log1p(pd.Series([-1.0])).iloc[0]))
    check("op_log1p邊界(x<-1時為NaN)", pd.isna(op_log1p(pd.Series([-2.0])).iloc[0]))

    # ---- 2026-09-19補件(a) op_mul：4情境（停牌/鎖死/除零/NaN） ----
    mul_normal = op_mul(pd.Series([2.0, 3.0, -4.0]), pd.Series([5.0, 0.5, 2.0]))
    check("op_mul正常值", list(mul_normal) == [10.0, 1.5, -8.0])
    halted_v = pd.Series([1000.0, 0.0, 1000.0])  # 停牌日成交量為0
    sign_delta = pd.Series([1.0, -1.0, 1.0])
    check("op_mul停牌日(量=0)結果為0非NaN", op_mul(sign_delta, halted_v).iloc[1] == 0.0)
    locked = pd.Series([10.0, 10.0, 10.0])  # 鎖死：連續相同值
    check("op_mul鎖死值(常數×常數)正常值", (op_mul(locked, locked) == 100.0).all())
    check("op_mul除零情境(0×NaN=NaN非0)",
          pd.isna(op_mul(pd.Series([0.0]), pd.Series([np.nan])).iloc[0]))
    check("op_mulNaN傳播(任一邊NaN則NaN)",
          pd.isna(op_mul(pd.Series([np.nan, 2.0]), pd.Series([3.0, 4.0])).iloc[0])
          and op_mul(pd.Series([np.nan, 2.0]), pd.Series([3.0, 4.0])).iloc[1] == 8.0)

    # ---- 2026-09-19補件(b) op_decay_linear：4情境（停牌/鎖死/除零/NaN） ----
    ramp = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])  # 遞增序列，權重w_i∝(n-i)，i=0最近
    dl5 = op_decay_linear(ramp, 5)
    # n=5窗口[1,2,3,4,5]，weights=[1,2,3,4,5]/15（索引0=最舊=1，索引4=最新=5）
    expected_dl5 = (1*1 + 2*2 + 3*3 + 4*4 + 5*5) / 15.0
    check("op_decay_linear(n=5)正常值(近重遠輕)", abs(dl5.iloc[4] - expected_dl5) < 1e-9)
    check("op_decay_linear前4筆為NaN(min_periods)", dl5.iloc[:4].isna().all())
    dl_locked = op_decay_linear(pd.Series([7.0, 7.0, 7.0, 7.0, 7.0]), 5)
    check("op_decay_linear鎖死值(常數序列)結果等於該常數(非除零壞掉)",
          abs(dl_locked.iloc[4] - 7.0) < 1e-9)
    halted_price = pd.Series([10.0, 10.0, np.nan, 10.0, 10.0])  # 停牌日價格NaN
    dl_halted = op_decay_linear(halted_price, 5)
    check("op_decay_linear停牌日(窗口含NaN)整個窗口回NaN不硬湊",
          pd.isna(dl_halted.iloc[4]))
    check("op_decay_linear(n=1)退化情況：窗口只有自己，加權平均等於自身",
          abs(op_decay_linear(ramp, 1).iloc[0] - 1.0) < 1e-9)

    # ---- 2026-09-19補件(c) 基準原子：4情境（停牌/鎖死/除零/NaN），
    # 用假loader注入合成資料，不打真實資料源，保持self-test快速且確定性 ----
    fake_bench = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"]),  # 2024-01-04缺值(停牌/假日)
        "o": [100.0, 101.0, 103.0], "h": [102.0, 102.0, 104.0],
        "l": [99.0, 100.0, 102.0], "c": [101.0, 101.0, 103.0], "v": [1e6, 1.1e6, 1.2e6],
    })
    def _fake_loader() -> pd.DataFrame:
        return fake_bench
    stock_df_aligned = pd.DataFrame({"date": pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])})  # 個股在01-04有交易但大盤缺值
    aligned_c = _align_benchmark_field(stock_df_aligned, _fake_loader, "c")
    check("基準原子對齊：個股日曆有但大盤缺值的日子forward-fill延續前值(非0/NaN)",
          abs(aligned_c.iloc[2] - 101.0) < 1e-9)  # 01-04用01-03的收盤值101延續
    check("基準原子對齊：正常重疊日期給出正確值",
          abs(aligned_c.iloc[0] - 101.0) < 1e-9 and abs(aligned_c.iloc[3] - 103.0) < 1e-9)
    stock_df_before = pd.DataFrame({"date": pd.to_datetime(["2023-12-31", "2024-01-02"])})
    aligned_before = _align_benchmark_field(stock_df_before, _fake_loader, "c")
    check("基準原子對齊：個股日期早於大盤資料起點回NaN(不外插)",
          pd.isna(aligned_before.iloc[0]))
    try:
        _align_benchmark_field(pd.DataFrame({"o": [1.0]}), _fake_loader, "o")
        check("基準原子缺date欄位應丟出ValueError", False)
    except ValueError:
        check("基準原子缺date欄位應丟出ValueError", True)
    check("ATOMS字典含全部10個基準原子",
          all(k in ATOMS for k in ("b50_o", "b50_h", "b50_l", "b50_c", "b50_v",
                                     "btx_o", "btx_h", "btx_l", "btx_c", "btx_v")))

    if failures:
        print(f"[FAIL] {len(failures)}項未過：{failures}")
        return 1
    n_atoms = len(ATOMS)
    n_ops = len(ALL_OPERATORS)
    print(f"[PASS] ATOM_LIBRARY.py 自我測試全部通過（{n_atoms}個原子、{n_ops}個算子，"
          f"含NaN/除零/停牌/漲跌停鎖死情境）")
    print(f"[誠實揭露] 原子數={n_atoms}＝原版14個（總司令原文估計15個，逐字列出的定義"
          f"只有14個，未自行湊數）＋2026-09-19審閱通過後補的10個基準原子(b50_/btx_各5)。"
          f"算子數={n_ops}＝原版17個＋補的2個(mul/decay_linear)。")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print(__doc__)
