# -*- coding: utf-8 -*-
"""每日排程更新 data/stock_detail.json 的「財報」區塊（EPS/毛利率/營益率/ROE），
取代個股頁財報分頁的 client-side FinMind 呼叫（STATUS.json列的P1項目）。

資料源（TWSE官方開放資料，免金鑰，跟fundamentals.json/margin_maintenance.json
同一套「最新一期全市場快照」模式）：
- `t187ap06_L_ci`：上市公司綜合損益表(一般業)——給營業收入/毛利/營業利益/
  歸屬母公司淨利/基本每股盈餘(EPS)。
- `t187ap07_L_ci`：上市公司資產負債表(一般業)——給歸屬母公司權益合計(ROE分母)。

**2026-08-27發現並修正的資料正確性問題（重要，不是外部限制，是這支腳本的bug）**：
1. `t187ap06_L_ci` 回傳的數值單位是「仟元」（跟月營收端點同一慣例），但原本
   這裡沒有乘1000——用回補歷史季度時交叉比對月營收總和才發現這個bug（見
   `research/build_stock_financials_history.py` 檔頭說明）。已修正：revenue/
   gross/op/net_income_parent全部乘1000對齊NT元，EPS本身是每股金額不用轉換。
2. **更關鍵**：TWSE官方季報格式對Q2/Q3是「累計數」（第二季報表其實是上半年
   累計、第三季報表是前三季累計），不是單季數字——用月營收交叉驗證發現：
   這支腳本原本直接把Q2的原始回傳值當成「單季」存進quarters陣列，實際上
   那是H1累計值（跟FinMind第三方整理過的單季數字混在同一個陣列裡會兜不起來，
   YoY/成長率計算會整個錯）。已修正：`main()`改成用「本次累計數 − 陣列裡
   已有的同年較早季度加總」還原成單季數字，同年較早季度缺的話就跳過不merge
   （寧可这一季暫時沒有，也不要塞一個算錯的單季數字進去）。
**已知限制，誠實揭露**：
1. 這兩個端點的 `_ci` 後綴是「一般業」分類，不含金融控股(_bd)/證券(_fh)/
   保險(_ins)/其他金融(_mim)——這些特殊產業的財報格式跟一般業不同，TWSE
   分開發布，這支腳本目前只處理一般業，金融股的財報分頁會維持FinMind路徑
   （見index.html的降級邏輯），不是這裡漏抓。
2. FCF（自由現金流）：TWSE/TPEx openapi都沒有現金流量表的開放資料端點（已
   查證兩邊swagger完整清單確認）；MOPS(mops.twse.com.tw)網頁查詢雖然有現金
   流量表，但2026-08-27重新實測其查詢端點(ajax_t164sb04)仍回傳「FOR SECURITY
   REASONS」反爬蟲阻擋，需要先走表單頁拿session/cookie才能過關——**這是重新
   驗證過的現況，不是沒查證就寫「永遠不可能」**，若之後要投入時間做這件事，
   需要處理MOPS的session/cookie流程，是可行但需要額外工程投入的方向，不是
   資料源不存在。個股頁財報分頁的FCF目前維持FinMind。
3. 跟月營收/PER一樣，這兩個端點只給「最新一期」全市場快照，用累積式寫回
   （每季只會新增一筆，讀repo裡已commit的stock_detail.json當底merge）。

2026-10-11 常備.開發-4 追加（不改動上面一般業流程的抓取與還原邏輯，只新增一段）：
上市金融業（金控 _fh／銀行 _basi／證券期貨 _bd／保險 _ins／異業 _mim）與
上櫃六類（TPEx `mopsfin_t187ap06_O_*`／`mopsfin_t187ap07_O_*`）由
`update_extra()` 處理，上面「已知限制 1」的金融業缺口自此補上。三來源查證
紀錄見 docs/DATA_SOURCE_MAP.md「上櫃／金融業財報」一節。這些端點同樣是累計數、
單位仟元；openapi 只給最新一季、歷史回補只到 2024Q4，2025Q1~2026Q1 的同年
較早季度不存在，所以另存 `latest_cum`（最新累計數），下一季起用「本季累計 −
上一季累計」還原單季，不再依賴 quarters 陣列有同年較早季度。
同日順手修正 ROE 單位 bug：權益是仟元、淨利已換算成元，原本直接相除讓 ROE
放大 1000 倍（2330 顯示 34777.78%）；`equity_parent_latest` 欄位本身維持仟元
不變（`shares_outstanding_approx` 刻意是仟股，供 generate_scores_future 與張數
對齊，不動）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "stock_detail.json"
TW_TZ = timezone(timedelta(hours=8))

INCOME_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
BALANCE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
QUARTERS_TO_KEEP = 8

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）。
RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        try:
            return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    state = _load_rate_limit_state()
    src = state["sources"].get(source, {})
    now = time.time()
    blocked_until = src.get("blocked_until")
    if blocked_until and now < blocked_until:
        remain_min = round((blocked_until - now) / 60, 1)
        raise RuntimeError(
            f"{source} 目前處於封鎖冷卻中（還剩約{remain_min}分鐘，"
            f"原因：{src.get('block_reason', '未知')}），依「資料源禮儀」規則拒絕發送請求"
        )
    last = src.get("last_request_at")
    if last and (now - last) < RATE_LIMIT_MIN_INTERVAL_SEC:
        time.sleep(RATE_LIMIT_MIN_INTERVAL_SEC - (now - last))
    src["last_request_at"] = time.time()
    state["sources"][source] = src
    _save_rate_limit_state(state)


import re as _re_secret

_SECRET_KEYS = r"token_tail|token|api_key|apikey|api_token|access_token|secret|password|authorization"
_SECRET_FIELD_RE = _re_secret.compile(
    r'"?(?:' + _SECRET_KEYS + r')"?\s*[:=]\s*(?:"(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^,}\s]*)',
    _re_secret.IGNORECASE,
)
_SECRET_FRAGMENT_RES = (
    _re_secret.compile(r"Bearer\s+\S+", _re_secret.IGNORECASE),
    _re_secret.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}(?:\.[\w-]*)?"),
    _re_secret.compile(r"[A-Za-z0-9_\-]{32,}"),
)


def _redact_secrets(text: str) -> str:
    """寫進會被commit的共用狀態檔（或任何log／例外訊息）前，先過濾 token_tail、
    金鑰欄位（含被 [:200] 截斷到沒有結尾引號的）與疑似金鑰片段（Bearer／JWT／32字元以上
    連續英數）。2026-10-02【先.十-四】：rate_limit_state.json 曾把 FinMind 402 回應的
    token_tail（金鑰末8碼）原文存進 block_reason 並 commit 進公開 repo。失敗一律 fail open
    成「整段遮蔽」，不得讓過濾本身中斷主流程（CLAUDE.md 十二節）。"""
    try:
        out = text or ""
        for rx in _SECRET_FRAGMENT_RES:
            out = rx.sub("[redacted-secret]", out)
        out = _SECRET_FIELD_RE.sub("[redacted-secret]", out)
        return out
    except Exception:  # noqa: BLE001
        return "[redacted-unparseable]"


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    detail = _redact_secrets(detail) if detail else detail
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _get_retry(url: str, source: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """official端點逾時/暫時性錯誤重試(指數退避)，2026-08-27新增——使用者指出
    「TWSE端點逾時目前是靜靜跳過」。4xx（含反爬蟲/IP封鎖）不重試，直接把該次
    response交給呼叫端自己的raise_for_status()處理，重試那類錯誤不會成功。
    2026-08-28新增`source`：發送前先過跨process共用節流/斷路檢查。"""
    _rate_limit_wait_or_raise(source)
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if r.status_code in (402, 403, 428, 429):
            _rate_limit_record_block(source, r.status_code, r.text[:200])
            raise RuntimeError(f"{source}回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


def _num(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_year_quarter(row: dict) -> tuple[int, int] | None:
    try:
        return int(row["年度"]) + 1911, int(row["季別"])
    except (KeyError, ValueError):
        return None


def load_existing() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "stocks": {}}


def fetch_income() -> dict[str, dict]:
    """回傳「TWSE官方原始回傳值」，**Q2/Q3是累計數（見檔頭2026-08-27說明），
    這裡先不做單季還原**——單季還原需要陣列裡已有的同年較早季度資料，
    要在 main() 裡跟既有 quarters 合併時才能做，這裡只負責忠實抓值+單位轉換
    （仟元→元）。回傳的key統一叫 `*_cum`，提醒呼叫端這是累計數，不能直接當
    單季用。"""
    r = _get_retry(INCOME_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap06_L_ci 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("公司代號")
        yq = _roc_year_quarter(row)
        revenue = _num(row.get("營業收入"))
        if not code or not yq or revenue is None:
            continue
        gross = _num(row.get("營業毛利（毛損）淨額"))
        op = _num(row.get("營業利益（損失）"))
        net_parent = _num(row.get("淨利（淨損）歸屬於母公司業主"))
        eps = _num(row.get("基本每股盈餘（元）"))
        # 2026-08-27修正：官方單位是仟元（跟月營收端點同慣例），原本沒乘1000。
        out[code] = {
            "year": yq[0], "quarter": yq[1],
            "revenue_cum": revenue * 1000,
            "gross_cum": gross * 1000 if gross is not None else None,
            "op_cum": op * 1000 if op is not None else None,
            "net_income_parent_cum": net_parent * 1000 if net_parent is not None else None,
            "eps_cum": eps,  # 每股金額本身不用轉換
        }
    return out


def discretize_quarter(existing_quarters: list[dict], cum: dict) -> dict | None:
    """把TWSE官方回傳的「累計數」(cum)還原成單季數字。Q1本身就是單季（累計==單季），
    Q2/Q3/Q4要減掉陣列裡已有的同年較早季度加總才是真正的單季數。如果較早季度
    缺資料（陣列裡同年份的季度數不夠），寧可回傳None跳過這次merge，也不要塞一個
    算錯的單季數字進去——這是2026-08-27用月營收交叉驗證抓到的真bug修正，不是
    自己憑空猜的邊界情況。"""
    y, q = cum["year"], cum["quarter"]
    if q == 1:
        revenue = cum["revenue_cum"]
        gross, op = cum["gross_cum"], cum["op_cum"]
        return {
            "year": y, "quarter": 1,
            "revenue": revenue,
            "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
            "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
            "net_income_parent": cum["net_income_parent_cum"],
            "eps": cum["eps_cum"],
        }
    prior = [r for r in existing_quarters if r.get("year") == y and r.get("quarter", 0) < q]
    if len(prior) < q - 1:
        return None  # 同年較早季度資料不齊，沒辦法安全還原成單季數
    prior_revenue = sum(r["revenue"] for r in prior)
    # gross/op只存了百分比，用「百分比x當季revenue」還原絕對值來加總——這是
    # 近似（受限於百分比只存到小數點後2位），但誤差在還原單季用途上可忽略。
    prior_gross = sum((r.get("revenue") or 0) * (r.get("gross_margin_pct") or 0) / 100 for r in prior)
    prior_op = sum((r.get("revenue") or 0) * (r.get("op_margin_pct") or 0) / 100 for r in prior)
    prior_net = sum(r.get("net_income_parent") or 0 for r in prior)
    prior_eps = sum(r.get("eps") or 0 for r in prior)
    revenue = cum["revenue_cum"] - prior_revenue
    gross = (cum["gross_cum"] - prior_gross) if cum["gross_cum"] is not None else None
    op = (cum["op_cum"] - prior_op) if cum["op_cum"] is not None else None
    net = (cum["net_income_parent_cum"] - prior_net) if cum["net_income_parent_cum"] is not None else None
    eps = (cum["eps_cum"] - prior_eps) if cum["eps_cum"] is not None else None
    return {
        "year": y, "quarter": q,
        "revenue": revenue,
        "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
        "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
        "net_income_parent": net,
        "eps": round(eps, 2) if eps is not None else None,
    }


def fetch_balance() -> dict[str, dict]:
    """2026-08-27新增（B17未來性濾網(a)類因子需要）：除了既有的
    `equity`（ROE分母），額外抓`common_stock_capital`（股本，台股普通股
    面額統一為每股新台幣10元，approx shares_outstanding = 股本/10，t187ap03_L
    的「已發行普通股數」只涵蓋部分公司，用股本反推更穩定）+
    `non_current_assets`（非流動資產，當「產能利用率」的分母代理——這個
    endpoint沒有單獨的「固定資產/不動產廠房及設備」欄位，非流動資產包含
    固定資產但也包含商譽/長期投資等，是刻意的簡化近似，不是精確的固定
    資產數字，誠實揭露）。回傳結構從原本`{code: equity}`改成
    `{code: {equity, common_stock_capital, non_current_assets}}`，呼叫端
    要跟著改。"""
    r = _get_retry(BALANCE_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap07_L_ci 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("公司代號")
        equity = _num(row.get("歸屬於母公司業主之權益合計"))
        if code and equity is not None:
            out[code] = {
                "equity": equity,
                "common_stock_capital": _num(row.get("股本")),
                "non_current_assets": _num(row.get("非流動資產")),
            }
    return out


# ── 2026-10-11 常備.開發-4：上市金融業＋上櫃財報 ─────────────────────────────
_TWSE = "https://openapi.twse.com.tw/v1/opendata/"
_TPEX = "https://www.tpex.org.tw/openapi/v1/"
# (端點名稱, 損益表URL, 資產負債表URL, 速率來源鍵, 產業格式)
EXTRA_SOURCES = [
    ("t187ap06_L_fh", _TWSE + "t187ap06_L_fh", _TWSE + "t187ap07_L_fh", "twse_openapi", "上市金控"),
    ("t187ap06_L_basi", _TWSE + "t187ap06_L_basi", _TWSE + "t187ap07_L_basi", "twse_openapi", "上市銀行"),
    ("t187ap06_L_bd", _TWSE + "t187ap06_L_bd", _TWSE + "t187ap07_L_bd", "twse_openapi", "上市證券期貨"),
    ("t187ap06_L_ins", _TWSE + "t187ap06_L_ins", _TWSE + "t187ap07_L_ins", "twse_openapi", "上市保險"),
    ("t187ap06_L_mim", _TWSE + "t187ap06_L_mim", _TWSE + "t187ap07_L_mim", "twse_openapi", "上市異業"),
    ("mopsfin_t187ap06_O_ci", _TPEX + "mopsfin_t187ap06_O_ci", _TPEX + "mopsfin_t187ap07_O_ci", "tpex_openapi", "上櫃一般業"),
    ("mopsfin_t187ap06_O_fh", _TPEX + "mopsfin_t187ap06_O_fh", _TPEX + "mopsfin_t187ap07_O_fh", "tpex_openapi", "上櫃金控"),
    ("mopsfin_t187ap06_O_basi", _TPEX + "mopsfin_t187ap06_O_basi", _TPEX + "mopsfin_t187ap07_O_basi", "tpex_openapi", "上櫃銀行"),
    ("mopsfin_t187ap06_O_bd", _TPEX + "mopsfin_t187ap06_O_bd", _TPEX + "mopsfin_t187ap07_O_bd", "tpex_openapi", "上櫃證券期貨"),
    ("mopsfin_t187ap06_O_ins", _TPEX + "mopsfin_t187ap06_O_ins", _TPEX + "mopsfin_t187ap07_O_ins", "tpex_openapi", "上櫃保險"),
    ("mopsfin_t187ap06_O_mim", _TPEX + "mopsfin_t187ap06_O_mim", _TPEX + "mopsfin_t187ap07_O_mim", "tpex_openapi", "上櫃異業"),
]
_PARENT_NI_KEYS = ("淨利（淨損）歸屬於母公司業主", "淨利（損）歸屬於母公司業主")
_EQUITY_KEYS = ("歸屬於母公司業主之權益合計", "歸屬於母公司業主之權益")


def _first(row: dict, keys) -> float | None:
    for k in keys:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _get_rows(url: str, source: str) -> list:
    r = _get_retry(url, source, timeout=40)
    r.raise_for_status()
    try:
        rows = r.json()
    except ValueError:
        raise RuntimeError(f"{url} 回傳非 JSON（可能是無效路徑回傳的HTML，已知地雷）")
    if not isinstance(rows, list):
        raise RuntimeError(f"{url} 回傳非預期格式")
    return rows


def _code_of(row: dict):
    return row.get("公司代號") or row.get("SecuritiesCompanyCode")


def _yq_of(row: dict):
    try:
        return int(row.get("年度") or row.get("Year")) + 1911, int(row.get("季別") or row.get("Season"))
    except (TypeError, ValueError):
        return None


def _close(a, b, tol=0.002) -> bool:
    return a is not None and b is not None and abs(a - b) <= max(1.0, abs(b) * tol)


def _checked_revenue_op(row: dict, label: str):
    """以會計恆等式驗證營收／營業利益欄位，兜不起來就回 (None, None)，不猜欄位。

    2026-10-11 實測地雷：TWSE t187ap06_L_fh（金控）表頭多一個「其他收益及費損淨額」、
    少一個所得稅欄，數值整段錯位一格（2880 的「淨收益」欄實際是呆帳費用）；
    保險業（_ins）營業收入−營業成本−營業費用≠營業利益。所以每一類都先驗再用。"""
    n = lambda k: _num(row.get(k))
    if label.endswith("金控"):
        a, b, net = n("利息淨收益"), n("利息以外淨收益"), n("淨收益")
        if _close((a or 0) + (b or 0), net) and a is not None:
            return net, None
        # 錯位版：「利息以外淨收益」欄裝的是淨收益（＝利息淨收益＋下一欄）
        c = n("其他收益及費損淨額")
        if a is not None and c is not None and _close(a + c, b):
            return b, None
        return None, None
    if label.endswith("銀行"):
        a, b, bad, opx, pre = (n("利息淨收益"), n("利息以外淨損益"), n("呆帳費用、承諾及保證責任準備提存"),
                               n("營業費用"), n("繼續營業單位稅前淨利（淨損）"))
        if None not in (a, b, bad, opx) and _close(a + b - bad - opx, pre):
            return a + b, None
        return None, None
    if label.endswith("證券期貨"):
        rev, exp, op = n("收益"), n("支出及費用"), n("營業利益")
        if None not in (rev, exp) and _close(rev - exp, op):
            return rev, op
        return None, None
    if label.endswith("異業"):
        rev, exp, pre = n("收入"), n("支出"), n("繼續營業單位稅前淨利（淨損）")
        if None not in (rev, exp) and _close(rev - exp, pre):
            return rev, None
        return None, None
    rev, op = n("營業收入"), n("營業利益（損失）")
    if label.endswith("保險"):
        cost, opx = n("營業成本"), n("營業費用")
        if None not in (rev, cost, opx) and _close(rev - cost - opx, op):
            return rev, op
        return None, None
    return rev, op  # 一般業：與上市一般業同欄位格式


def parse_extra_income(row: dict, label: str = "") -> dict | None:
    """把各產業損益表列轉成跟一般業相同的累計數 dict（仟元→元）。
    營收／營業利益須通過 _checked_revenue_op 恆等式驗證，否則留 None；EPS 與歸屬母公司淨利照收。"""
    yq = _yq_of(row)
    revenue, op = _checked_revenue_op(row, label)
    eps0 = _num(row.get("基本每股盈餘（元）"))
    if not yq or (revenue is None and eps0 is None):
        return None
    gross = _num(row.get("營業毛利（毛損）淨額")) if label.endswith("一般業") else None
    net = _first(row, _PARENT_NI_KEYS)
    if net is None:
        # 無子公司的公司（例如部分保險業）歸屬母公司欄位留空；此時無非控制權益，本期淨利即歸屬母公司
        net = _num(row.get("本期淨利（淨損）"))
    eps = _num(row.get("基本每股盈餘（元）"))

    def k(v):
        return v * 1000 if v is not None else None
    return {"year": yq[0], "quarter": yq[1], "revenue_cum": k(revenue), "gross_cum": k(gross),
            "op_cum": k(op), "net_income_parent_cum": k(net), "eps_cum": eps}


def discretize_from_cum(prev_cum: dict | None, cum: dict) -> dict | None:
    """用「上一季累計」還原單季：同年 q-1 的累計數存在時，單季＝本季累計−上一季累計。"""
    if not prev_cum or prev_cum.get("year") != cum["year"] or prev_cum.get("quarter") != cum["quarter"] - 1:
        return None

    def d(a, b):
        return (a - b) if a is not None and b is not None else None
    revenue = d(cum["revenue_cum"], prev_cum.get("revenue_cum"))
    gross, op = d(cum["gross_cum"], prev_cum.get("gross_cum")), d(cum["op_cum"], prev_cum.get("op_cum"))
    eps = d(cum["eps_cum"], prev_cum.get("eps_cum"))
    return {
        "year": cum["year"], "quarter": cum["quarter"], "revenue": revenue,
        "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
        "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
        "net_income_parent": d(cum["net_income_parent_cum"], prev_cum.get("net_income_parent_cum")),
        "eps": round(eps, 2) if eps is not None else None,
    }


def apply_cum(fin: dict, cum: dict, source: str, label: str) -> bool:
    """寫入 latest_cum 並盡量還原單季併入 quarters；回傳是否有新增／更新單季。"""
    prev = fin.get("latest_cum")
    same_q = prev and (prev.get("year"), prev.get("quarter")) == (cum["year"], cum["quarter"])
    prev_for_diff = fin.get("prev_cum") if same_q else prev  # 同一季重跑：沿用上次用來差分的那份
    discrete = None
    if cum["quarter"] == 1:
        r, g, o = cum["revenue_cum"], cum["gross_cum"], cum["op_cum"]
        discrete = {"year": cum["year"], "quarter": 1, "revenue": r,
                    "gross_margin_pct": round(g / r * 100, 2) if g is not None and r else None,
                    "op_margin_pct": round(o / r * 100, 2) if o is not None and r else None,
                    "net_income_parent": cum["net_income_parent_cum"], "eps": cum["eps_cum"]}
    if discrete is None:
        discrete = discretize_from_cum(prev_for_diff, cum)
    if discrete is None and cum["revenue_cum"] is not None:
        try:
            discrete = discretize_quarter(fin.get("quarters", []), cum)
        except (TypeError, KeyError):  # 舊季度缺營收欄位時無法安全相減，寧可不還原
            discrete = None
    fin["prev_cum"] = prev_for_diff
    fin["latest_cum"] = dict(cum, source=source, industry=label)
    fin["source"] = source
    fin["industry_format"] = label
    if discrete is None:
        return False
    fin["quarters"] = merge_quarters(fin.get("quarters", []), discrete)
    return True


def update_extra(stocks: dict) -> tuple[dict, list]:
    """逐一處理 EXTRA_SOURCES；單一端點失敗只記錯誤、不影響其他端點（十二）。"""
    stats, errors = {}, []
    for name, inc_url, bal_url, rl_src, label in EXTRA_SOURCES:
        try:
            inc_rows = _get_rows(inc_url, rl_src)
            bal_rows = _get_rows(bal_url, rl_src)
            bal = {}
            for row in bal_rows:
                c = _code_of(row)
                if c:
                    bal[c] = {"equity": _first(row, _EQUITY_KEYS), "common_stock_capital": _num(row.get("股本")),
                              "non_current_assets": _num(row.get("非流動資產"))}
            n_cum = n_q = 0
            for row in inc_rows:
                c, cum = _code_of(row), parse_extra_income(row, label)
                if not c or not cum:
                    continue
                fin = stocks.setdefault(c, {}).setdefault("financials", {})
                n_cum += 1
                if apply_cum(fin, cum, name, label):
                    n_q += 1
                b = bal.get(c) or {}
                if b.get("equity") is not None:
                    fin["equity_parent_latest"] = b["equity"]  # 仟元，與一般業欄位同單位
                    qs = fin.get("quarters", [])
                    fresh = bool(qs) and (qs[-1].get("year"), qs[-1].get("quarter")) == (cum["year"], cum["quarter"])
                    # 單季資料沒跟上最新一季時（2025Q1~2026Q1 斷層），不拿舊四季配新權益硬算 ROE
                    fin["roe_ttm_pct"] = compute_roe_ttm(qs, b["equity"] * 1000) if fresh else None
                if b.get("common_stock_capital"):
                    fin["shares_outstanding_approx"] = round(b["common_stock_capital"] / 10, 0)  # 仟股，同一般業
                if b.get("non_current_assets") is not None:
                    fin["non_current_assets_latest"] = b["non_current_assets"]
            stats[name] = {"rows": len(inc_rows), "cum": n_cum, "quarters_updated": n_q}
        except Exception as e:
            print(f"[warn] {name} 失敗：{e}")
            errors.append(f"{name}: {_redact_secrets(str(e))[:200]}")
    return stats, errors


def merge_quarters(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = list(existing or [])
    rows = [r for r in rows if not (r.get("year") == latest["year"] and r.get("quarter") == latest["quarter"])]
    rows.append(latest)
    rows.sort(key=lambda r: (r["year"], r["quarter"]))
    return rows[-QUARTERS_TO_KEEP:]


def compute_roe_ttm(quarters: list[dict], equity_latest: float | None) -> float | None:
    last4 = [q for q in quarters if q.get("net_income_parent") is not None][-4:]
    if len(last4) < 4 or not equity_latest:
        return None
    ttm_ni = sum(q["net_income_parent"] for q in last4)
    return round(ttm_ni / equity_latest * 100, 2)


def main():
    payload = load_existing()
    stocks = payload.setdefault("stocks", {})

    errors = []
    income_updated = 0
    skipped_no_baseline = 0
    try:
        income = fetch_income()
        equity = fetch_balance()
        for code, cum in income.items():
            entry = stocks.setdefault(code, {})
            fin = entry.setdefault("financials", {})
            existing_quarters = fin.get("quarters", [])
            discrete = discretize_quarter(existing_quarters, cum)
            if discrete is None:
                skipped_no_baseline += 1
                continue
            fin["quarters"] = merge_quarters(existing_quarters, discrete)
            bal = equity.get(code) or {}
            eq = bal.get("equity")
            fin["equity_parent_latest"] = eq
            fin["roe_ttm_pct"] = compute_roe_ttm(fin["quarters"], eq * 1000 if eq else None)  # 權益仟元→元（2026-10-11 修正）
            fin["source"] = "t187ap06_L_ci"
            fin["industry_format"] = "上市一般業"
            fin["latest_cum"] = dict(cum, source="t187ap06_L_ci", industry="上市一般業")
            capital = bal.get("common_stock_capital")
            fin["shares_outstanding_approx"] = round(capital / 10, 0) if capital else None
            fin["non_current_assets_latest"] = bal.get("non_current_assets")
        income_updated = len(income) - skipped_no_baseline
    except Exception as e:
        print(f"財報(income/balance) 更新失敗：{e}")
        errors.append(f"financials: {e}")

    # 2026-10-11 常備.開發-4：上市金融業＋上櫃財報（獨立 try，失敗不影響上面一般業結果）
    extra_stats = {}
    try:
        extra_stats, extra_errors = update_extra(stocks)
        errors.extend(extra_errors)
    except Exception as e:
        print(f"[warn] 上櫃／金融業財報更新失敗：{e}")
        errors.append(f"financials_extra: {e}")

    payload.setdefault("meta", {})
    payload["meta"]["financials_extra_source"] = "TWSE openapi t187ap06/07_L_{fh,basi,bd,ins,mim}（上市金融業）＋TPEx openapi mopsfin_t187ap06/07_O_{ci,fh,basi,bd,ins,mim}（上櫃）"
    payload["meta"]["financials_extra_stats"] = extra_stats
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["source"] = "TWSE openapi t187ap06_L_ci/t187ap07_L_ci（財報）+ TWSE T86/TPEx tpex_3insti_daily_trading（三大法人）+ TWSE MI_MARGN/TPEx tpex_mainboard_margin_balance（融資融券），各由market.yml不同步驟合併寫入"  # 2026-09-03（P0三-三.3）
    payload["meta"]["financials_source"] = "TWSE openapi t187ap06_L_ci(綜合損益表-一般業) + t187ap07_L_ci(資產負債表-一般業)"
    payload["meta"]["financials_updated_count"] = income_updated
    payload["meta"]["financials_skipped_no_baseline_count"] = skipped_no_baseline
    payload["meta"].setdefault("errors", [])
    payload["meta"]["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：財報更新 {income_updated} 檔，{skipped_no_baseline} 檔因缺同年較早季度"
          f"基準無法安全還原單季數字而跳過（合計 {len(stocks)} 檔有任何資料）")
    if errors:
        print(f"部分失敗（不中止）：{errors}")


if __name__ == "__main__":
    main()
