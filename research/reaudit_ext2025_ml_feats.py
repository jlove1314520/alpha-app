# -*- coding: utf-8 -*-
"""先.一五五-2 F14 用：把 #483 的 10 個價量特徵延長到 2025 起（零新外部請求）。

公式逐行照 factors.py::prepare_factors() 的價量段（常數從 factors import，不改原檔）；
輸入＝reaudit_ext2025_engine.load_extended() 的延長價（2025 起用「漲跌」欄還原）＋延長後加權指數收盤。
核對：2024 底以前算出的值要與 reaudit_ssu_loaded.pkl 原欄一致（不一致就不採用重算值，只在 2025 起用）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import factors as FX

FEATURES = ["f_low_vol", "f_idio_vol", "f_bab", "f_short_reversal_1m", "f_short_term_reversal_1w", "f_amihud_illiq",
            "f_52w_high_prox", "f_residual_momentum", "f_rel_strength", "f_ma_breakout"]


def compute(d: pd.DataFrame, mkt_close: pd.Series) -> pd.DataFrame:
    """d：單檔延長價（字串 date、adj_close、Trading_Volume、Trading_money），回傳 10 欄特徵（同列序）。"""
    d = d.sort_values("date").reset_index(drop=True)
    o = pd.DataFrame(index=d.index)
    mc = d["date"].map(mkt_close)
    px = d["adj_close"].astype(float)
    ret60 = px / px.shift(FX.REL_STRENGTH_WINDOW) - 1
    o["f_rel_strength"] = ret60 - (mc / mc.shift(FX.REL_STRENGTH_WINDOW) - 1)
    ma60 = px.rolling(FX.MA_WINDOW, min_periods=FX.MA_WINDOW).mean()
    vol20 = d["Trading_Volume"].rolling(FX.VOL_SHORT_WINDOW, min_periods=FX.VOL_SHORT_WINDOW).mean()
    vol60 = d["Trading_Volume"].rolling(FX.VOL_LONG_WINDOW, min_periods=FX.VOL_LONG_WINDOW).mean()
    o["f_ma_breakout"] = (px / ma60 - 1) * (vol20 / vol60)
    r = px.pct_change()
    W = FX.LOW_VOL_WINDOW
    o["f_low_vol"] = -r.rolling(W, min_periods=W).std()
    o["f_short_reversal_1m"] = -(px / px.shift(FX.SHORT_REVERSAL_WINDOW) - 1)
    il = np.where(d["Trading_money"] > 0, r.abs() / d["Trading_money"], np.nan)
    o["f_amihud_illiq"] = pd.Series(il, index=d.index).rolling(FX.AMIHUD_WINDOW, min_periods=FX.AMIHUD_WINDOW).mean()
    mr = mc.pct_change()
    vs, vm = r.rolling(W, min_periods=W).var(), mr.rolling(W, min_periods=W).var()
    b60 = r.rolling(W, min_periods=W).cov(mr) / vm
    o["f_idio_vol"] = -np.sqrt((vs - b60 ** 2 * vm).clip(lower=0.0))
    o["f_bab"] = -b60
    R = FX.RESIDUAL_MOMENTUM_WINDOW
    b252 = r.rolling(R, min_periods=R).cov(mr) / mr.rolling(R, min_periods=R).var()
    o["f_residual_momentum"] = (px / px.shift(R) - 1) - b252 * (mc / mc.shift(R) - 1)
    o["f_52w_high_prox"] = px / px.rolling(FX.HIGH_52W_WINDOW, min_periods=FX.HIGH_52W_WINDOW).max()
    o["f_short_term_reversal_1w"] = -(px / px.shift(FX.SHORT_TERM_REVERSAL_1W_WINDOW) - 1)
    return o[FEATURES]
