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

import os
import sys
import contextlib
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

# 2026-10-21 先.一二五-1（總司令核准 先.一二三-1 甲案）：同年較早季度缺時，改拿 App 顯示用回補檔
# （FinMind 逐檔單季，單位元）當減數基準。回補檔在 research/validation/holdout.py DISPLAY_ONLY_DATA_FILES，
# 這裡是 App 顯示端（.github/scripts），寫進 stock_detail.json 的值一律標 source 讓研究端可辨識。
BACKFILL_PATH = REPO_ROOT / "data" / "financials_backfill.json"
SRC_Q_FROM_BACKFILL = "q1_from_backfill"            # 直接取自回補檔的基準季
SRC_RESTORED_WITH_BACKFILL = "official_cum_minus_backfill"  # 官方累計數減回補檔基準季還原的單季
BACKFILL_MAX_DIFF = 0.01  # 還原單季 vs 回補檔同季單季，營收／歸母淨利相對差上限
BACKFILL_EPS_ABS_TOL = 0.02  # EPS 兩邊都只到小數 2 位，1% 對小 EPS 沒意義，改用絕對容差 [自行裁量]

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）。
RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60


RATE_LIMIT_LOCK_PATH = RATE_LIMIT_STATE_PATH.with_name(RATE_LIMIT_STATE_PATH.name + ".lock")


@contextlib.contextmanager
def _rate_limit_lock(timeout: float = 15.0, stale_sec: float = 60.0):
    """修.FinMind計數（2026-10-15）：跨行程檔案鎖（O_CREAT|O_EXCL 建 .lock 檔），保護共用狀態檔的
    「讀→改→寫」，避免兩支行程互相覆寫 calls_by_minute／last_request_at（10/15 08:08 撞 402 時狀態檔只記 1～11 次）。
    超過 stale_sec 的鎖視為前一個行程死掉留下的，直接清掉；等不到鎖或建鎖失敗只印警告、不加鎖照常進行
    （fail open，CLAUDE.md 十二節）。各腳本自成一體複製這段（不跨目錄 import 的既有慣例）。"""
    fd = None
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(RATE_LIMIT_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                if time.time() - RATE_LIMIT_LOCK_PATH.stat().st_mtime > stale_sec:
                    RATE_LIMIT_LOCK_PATH.unlink()
                    continue
            except OSError:
                pass  # 鎖剛好被別人釋放／正在刪，下一圈重試
            if time.time() > deadline:
                print(f"[rate_limit] 警告：{timeout:.0f} 秒等不到 {RATE_LIMIT_LOCK_PATH.name}，本次不加鎖照常進行", file=sys.stderr)
                break
            time.sleep(0.05)
        except Exception as e:  # noqa: BLE001 -- 鎖本身失敗只降級成警告（十二節）
            print(f"[rate_limit] 警告：建鎖失敗（{e!r}），本次不加鎖照常進行", file=sys.stderr)
            break
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
                RATE_LIMIT_LOCK_PATH.unlink()
            except OSError as e:
                print(f"[rate_limit] 警告：釋放鎖失敗（{e!r}），{stale_sec:.0f} 秒後會被視為過期鎖清掉", file=sys.stderr)


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        for _ in range(3):  # 修.FinMind計數：別的行程正在換檔時可能讀到半份，稍等重讀，避免拿空狀態蓋掉全部來源
            try:
                return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                time.sleep(0.05)
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    """修.FinMind計數：先寫暫存檔再 os.replace（原子換檔），別的行程不會讀到寫一半的 JSON；
    Windows 上目標檔被開著時 replace 可能 PermissionError，重試 5 次後退回直接覆寫。"""
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2)
    tmp = RATE_LIMIT_STATE_PATH.with_name(f"{RATE_LIMIT_STATE_PATH.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(tmp, RATE_LIMIT_STATE_PATH)
                return
            except PermissionError:
                time.sleep(0.05)
    except Exception as e:  # noqa: BLE001 -- 原子寫入失敗退回直接覆寫（十二節）
        print(f"[rate_limit] 警告：原子寫入失敗（{e!r}），改直接覆寫", file=sys.stderr)
    try:
        tmp.unlink()
    except OSError:
        pass
    RATE_LIMIT_STATE_PATH.write_text(text, encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    # 修.FinMind計數：鎖內「重讀→判斷→只改自己這個來源→寫回」；間隔不夠就放開鎖去睡，醒來重讀再判斷，
    # 不再拿睡前讀到的舊狀態整份寫回（那會蓋掉別的行程在這段時間寫進去的計數）。
    while True:
        with _rate_limit_lock():
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
            wait = (RATE_LIMIT_MIN_INTERVAL_SEC - (now - last)) if last else 0.0
            if wait <= 0:
                src["last_request_at"] = now
                state["sources"][source] = src
                _save_rate_limit_state(state)
                return
        time.sleep(wait)


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


def _rate_limit_record_block(*args, **kwargs) -> None:
    """修.FinMind計數：在跨行程鎖內做「重讀→標封鎖→寫回」（參數原樣轉給 _rate_limit_record_block_unlocked）。"""
    with _rate_limit_lock():
        _rate_limit_record_block_unlocked(*args, **kwargs)


def _rate_limit_record_block_unlocked(source: str, status_code: int, detail: str = "") -> None:
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
        net_parent = _first(row, _PARENT_NI_KEYS)
        if net_parent is None:
            # 先.一三五-1mj（2026-11-07）：無子公司的公司歸屬母公司欄位留空（上市一般業 61/1039 檔缺、上櫃同路徑 0/890 缺），
            # 比照 parse_extra_income 用本期淨利；但非控制權益欄有非零值時不回退（本期淨利會含非控制權益）。
            nci = _first(row, ("淨利（淨損）歸屬於非控制權益", "淨利（損）歸屬於非控制權益"))
            if not nci:
                net_parent = _num(row.get("本期淨利（淨損）"))
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
    # 2026-10-21 先.一二五-1 順手修：較早季度某欄位是 None 時，上面 `or 0` 會把累計數整筆當單季（例：1540 歸母淨利），
    # 該欄位改回 None，寧可空也不寫錯值。
    if any(r.get("net_income_parent") is None for r in prior):
        net = None
    if any(r.get("eps") is None for r in prior):
        eps = None
    if any(r.get("gross_margin_pct") is None and r.get("revenue") for r in prior):
        gross = None
    if any(r.get("op_margin_pct") is None and r.get("revenue") for r in prior):
        op = None
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
                    fin.pop("shares_basis", None)  # 先.一三五-1my：股本÷10 重寫後，舊的推得股數標記失效，交給 fix_shares_by_implied_eps 重判
                    fin.pop("shares_from_capital_div10", None)
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
    # 2026-10-30 先.一三五-1cc（純 bug 修復）：四季必須連續；中間某季淨利是 None 時舊版會跨過缺口
    # 拿更早的季度湊滿四季（實測 77 檔，例 7822 用 2023Q4／2024Q4／2026Q1／2026Q2），寧可空也不寫錯值。
    idx = [q["year"] * 4 + q["quarter"] for q in last4]
    if idx[-1] - idx[0] != 3:
        return None
    ttm_ni = sum(q["net_income_parent"] for q in last4)
    return round(ttm_ni / equity_latest * 100, 2)


def clear_stale_nonconsecutive_roe(stocks: dict) -> list[str]:
    """2026-10-30 先.一三五-1ce（純 bug 修復）：1cc 只修了「本班有重算」的檔；本班官方表沒有的代號
    （例 1293／2311 只有半年報季度、最後一季停在 2024）沿用舊檔裡舊版跨缺口算出的 roe_ttm_pct（實測 38 檔）。
    這裡對全檔再驗一次：近四個有淨利的季度不連續就清成 None（寧可空也不寫錯值），回傳被清掉的代號。"""
    cleared = []
    for code, s in stocks.items():
        fin = (s or {}).get("financials") if isinstance(s, dict) else None
        if not isinstance(fin, dict) or fin.get("roe_ttm_pct") is None:
            continue
        last4 = [q for q in (fin.get("quarters") or []) if isinstance(q, dict) and q.get("net_income_parent") is not None][-4:]
        try:
            idx = [int(q["year"]) * 4 + int(q["quarter"]) for q in last4]
        except Exception:
            idx = []
        if len(idx) < 4 or idx[-1] - idx[0] != 3:
            fin["roe_ttm_pct"] = None
            cleared.append(str(code))
    return sorted(cleared)


def load_backfill() -> dict:
    """讀回補檔 stocks；讀不到只降級成空 dict（十二節：輔助來源失敗不得中斷主流程）。"""
    try:
        return json.loads(BACKFILL_PATH.read_text(encoding="utf-8")).get("stocks", {}) or {}
    except Exception as e:
        print(f"[warn] 讀 {BACKFILL_PATH.name} 失敗，缺基準照舊跳過：{e}")
        return {}


def _rel_diff(a, b) -> float | None:
    if a is None or b is None:
        return None
    if b == 0:
        return 0.0 if a == 0 else float("inf")
    return abs(a - b) / abs(b)


def restore_with_backfill(existing_quarters: list[dict], cum: dict, bf_rows: list[dict]) -> tuple[list[dict] | None, str]:
    """缺同年較早季度時，用回補檔的同年較早季度當基準還原單季。
    回傳 (要 merge 的季度列表, 說明)；不寫時列表為 None。回補檔與官方都是元（fetch_income 已 ×1000），不另換算。"""
    y, q = cum["year"], cum["quarter"]
    have = {(r.get("year"), r.get("quarter")) for r in existing_quarters}
    bf = {(r.get("year"), r.get("quarter")): r for r in bf_rows or []}
    base = []
    for pq in range(1, q):
        if (y, pq) in have:
            base.append(next(r for r in existing_quarters if (r.get("year"), r.get("quarter")) == (y, pq)))
        elif (y, pq) in bf and bf[(y, pq)].get("revenue") is not None:
            base.append(dict(bf[(y, pq)], source=SRC_Q_FROM_BACKFILL))
        else:
            return None, f"回補檔缺 {y}Q{pq}"
    discrete = discretize_quarter(base, cum)
    if discrete is None:
        return None, "基準仍不齊"
    ref = bf.get((y, q))
    if ref:
        checks = {
            "revenue": _rel_diff(discrete.get("revenue"), ref.get("revenue")),
            "net_income_parent": _rel_diff(discrete.get("net_income_parent"), ref.get("net_income_parent")),
        }
        bad = [f"{k} 差 {v:.2%}" for k, v in checks.items() if v is not None and v > BACKFILL_MAX_DIFF]
        if discrete.get("eps") is not None and ref.get("eps") is not None and abs(discrete["eps"] - ref["eps"]) > BACKFILL_EPS_ABS_TOL:
            bad.append(f"eps {discrete['eps']} vs {ref['eps']}")
        if bad:
            return None, "與回補檔同季不符：" + "；".join(bad)
    discrete["source"] = SRC_RESTORED_WITH_BACKFILL
    return [b for b in base if b.get("source") == SRC_Q_FROM_BACKFILL] + [discrete], "ok"


def merge_backfill_display_quarters(stocks: dict, backfill: dict) -> dict:
    """2026-11-06 先.一三五-1lw（純 bug 修復）：官方 openapi 只給「最新一季累計數」，缺同年基準季的檔
    單季序列會停在很久以前（實測 669 檔停在 2024Q4，但回補檔已有到 2026Q2）。這裡把回補檔裡
    「官方 quarters 沒有」的季度直接併進 quarters（App 顯示用），規則：
    - 官方已有的季度一律不覆蓋（同季官方優先）；只補「比現有最早季更新」的季度（包含中間缺口與更新的季）。
    - 補進來的季度標 source=q1_from_backfill（研究端 DISPLAY_ONLY_DERIVED_SOURCES 已排除；App 已照實標「取自 FinMind 季報回補」）。
    - 安全檢查：若官方 latest_cum 那一年回補檔 Q1..Qn 都有，加總要對得上官方累計（營收／歸母淨利相對差
      ≤BACKFILL_MAX_DIFF、EPS 差 ≤BACKFILL_EPS_ABS_TOL×n）；對不上就整檔不併（寧可舊，不顯示錯的）。
      先.一三五-1mc：只有 EPS 對不上、營收與歸母淨利都核對得到且一致時放行（股數變動），記在 eps_mismatch_passed。
    回傳統計；自身出錯只略過該檔（十二節）。"""
    stats = {"merged_codes": [], "rows_added": 0, "rejected": {}, "eps_mismatch_passed": {}}
    for code, s in stocks.items():
        try:
            bf_rows = backfill.get(str(code)) if isinstance(backfill, dict) else None
            fin = (s or {}).get("financials") if isinstance(s, dict) else None
            if not bf_rows or not isinstance(fin, dict):
                continue
            qs = [r for r in (fin.get("quarters") or []) if isinstance(r, dict)]
            if not qs:
                continue
            have = {(r.get("year"), r.get("quarter")) for r in qs}
            earliest = min(int(r["year"]) * 4 + int(r["quarter"]) for r in qs)
            bf = {(int(r["year"]), int(r["quarter"])): r for r in bf_rows
                  if isinstance(r, dict) and r.get("year") and r.get("quarter")}
            lc = fin.get("latest_cum") or {}
            ly, lq = lc.get("year"), lc.get("quarter")
            if ly and lq and all((ly, k) in bf for k in range(1, lq + 1)):
                rows = [bf[(ly, k)] for k in range(1, lq + 1)]
                bad = []
                verified = set()  # 營收／淨利實際核對過（兩邊都有值）且 ≤上限的項目
                for key, ck in (("revenue", "revenue_cum"), ("net_income_parent", "net_income_parent_cum")):
                    vals = [r.get(key) for r in rows]
                    if lc.get(ck) is not None and None not in vals:
                        d = _rel_diff(sum(vals), lc[ck])
                        if d is not None and d > BACKFILL_MAX_DIFF:
                            bad.append(f"{key} 加總差 {d:.2%}")
                        elif d is not None:
                            verified.add(key)
                eps = [r.get("eps") for r in rows]
                eps_msg = None
                if lc.get("eps_cum") is not None and None not in eps and abs(sum(eps) - lc["eps_cum"]) > BACKFILL_EPS_ABS_TOL * lq:
                    eps_msg = f"eps 加總 {round(sum(eps), 2)} vs 官方累計 {lc['eps_cum']}"
                # 先.一三五-1mc（2026-11-07）：累計 EPS 用加權平均股數，期中增資／減資時單季 EPS 加總本來就不等於累計，
                # EPS 差不代表回補檔錯。營收與歸母淨利「都核對得到且 ≤上限」時，EPS 差只記在 eps_mismatch_passed、不擋；
                # 淨利核對不到（任一邊缺值）的照舊擋，避免只憑營收放行。
                if eps_msg:
                    if not bad and verified >= {"revenue", "net_income_parent"}:
                        stats["eps_mismatch_passed"][str(code)] = eps_msg
                    else:
                        if "net_income_parent" not in verified and not bad:
                            eps_msg += "（歸母淨利無法核對，不放行）"
                        bad.append(eps_msg)
                if bad:
                    stats["rejected"][str(code)] = "；".join(bad)
                    continue
            added = []
            for (y, q), r in bf.items():
                if (y, q) in have or y * 4 + q < earliest:
                    continue
                if r.get("revenue") is None and r.get("eps") is None:
                    continue
                added.append({"year": y, "quarter": q, "revenue": r.get("revenue"),
                              "gross_margin_pct": r.get("gross_margin_pct"), "op_margin_pct": r.get("op_margin_pct"),
                              "net_income_parent": r.get("net_income_parent"), "eps": r.get("eps"),
                              "source": SRC_Q_FROM_BACKFILL})
            if not added:
                continue
            merged = sorted(qs + added, key=lambda r: (r["year"], r["quarter"]))[-QUARTERS_TO_KEEP:]
            fin["quarters"] = merged
            stats["merged_codes"].append(str(code))
            stats["rows_added"] += len(added)
        except Exception as e:  # 單檔出錯只略過（十二節）
            stats["rejected"][str(code)] = f"合併失敗：{e}"
    stats["merged_codes"].sort()
    return stats


def _codes_with_backfill_quarters(stocks: dict) -> list[str]:
    """先.一三五-1md：quarters 裡帶 q1_from_backfill 季度的代號（含先前輪次已併入、本輪沒有新增的檔）。"""
    out = []
    for c, s in stocks.items():
        try:
            if any(isinstance(r, dict) and r.get("source") == SRC_Q_FROM_BACKFILL
                   for r in (((s or {}).get("financials") or {}).get("quarters") or [])):
                out.append(str(c))
        except Exception:
            continue
    return out


def recompute_roe_after_backfill_merge(stocks: dict, codes) -> dict:
    """2026-11-07 先.一三五-1md（純 bug 修復）：compute_roe_ttm() 原本在併入回補季之前算，只用官方季度；
    1lw 併入回補季後（例 2883 季度已到 2026Q2），roe_ttm_pct 還是舊值或 None（分子停在 2024、分母是最新權益）。
    這裡對「quarters 帶回補季」的檔（含先前輪次已併入的），用合併後近四季重算一次：
    - 要有 equity_parent_latest（仟元→元，同 main() 的換算）與 latest_cum；
    - 最後一個有淨利的季度必須等於 latest_cum 那一季（權益與分子同一期），否則清成 None（不拿舊四季配新權益）；
    - 四季連續由 compute_roe_ttm() 把關（不連續回 None）。
    單檔出錯只略過（十二節）。回傳統計。"""
    st = {"recomputed": [], "set_none": [], "errors": {}}
    for code in codes or []:
        try:
            fin = ((stocks.get(code) or stocks.get(str(code)) or {}).get("financials"))
            if not isinstance(fin, dict):
                continue
            eq = fin.get("equity_parent_latest")
            lc = fin.get("latest_cum") or {}
            if not eq or not lc.get("year") or not lc.get("quarter"):
                continue
            ni_qs = [q for q in (fin.get("quarters") or []) if isinstance(q, dict) and q.get("net_income_parent") is not None]
            fresh = bool(ni_qs) and (int(ni_qs[-1]["year"]), int(ni_qs[-1]["quarter"])) == (int(lc["year"]), int(lc["quarter"]))
            val = compute_roe_ttm(ni_qs, eq * 1000) if fresh else None
            fin["roe_ttm_pct"] = val
            (st["recomputed"] if val is not None else st["set_none"]).append(str(code))
        except Exception as e:
            st["errors"][str(code)] = str(e)[:200]
    return st


def load_month_revenue_map(path: Path | None = None) -> dict:
    """先.一三五-1me：讀 data/fundamentals.json 的月營收（元，month_revenue＋revenue_history_scoring），回 {代號: {(年, 月): 營收}}。零外部請求；讀不到回空 dict。"""
    path = path or (REPO_ROOT / "data" / "fundamentals.json")
    out: dict = {}
    try:
        f = json.loads(path.read_text(encoding="utf-8")).get("fundamentals") or {}
        for code, v in f.items():
            m = {}
            # month_revenue 優先；只保留 8 個月的檔再用 revenue_history_scoring（26 個月）補（先.一三五-1me）
            for r in ((v or {}).get("month_revenue") or []) + ((v or {}).get("revenue_history_scoring") or []):
                try:
                    rev = _num(r.get("revenue"))  # 千分位安全（稽核 g_comma_parsing）
                    if rev is not None:
                        m.setdefault((int(r["year"]), int(r["month"])), rev)
                except (TypeError, ValueError, KeyError):
                    continue
            if m:
                out[str(code)] = m
    except Exception as e:  # 讀不到月營收只是少一種證明，不擋流程（十二節）
        print(f"[warn] 讀月營收失敗（半年報證明只用結構規則）：{e}")
    return out


HALF_YEAR_REV_TOL = 0.005  # 營收與月營收加總相對差 ≤0.5% 才算對上


def _month_sum(mr: dict, year: int, months) -> float | None:
    vals = [mr.get((year, m)) for m in months]
    return None if not mr or any(v is None for v in vals) else sum(vals)


def _close(a, b) -> bool:
    try:
        return a is not None and b is not None and b != 0 and abs(a - b) <= HALF_YEAR_REV_TOL * abs(b)
    except TypeError:
        return False


def tag_half_year_periods(stocks: dict, month_rev: dict | None = None) -> dict:
    """先.一三五-1mb（2026-11-07）：半年報公司（興櫃／創新板時期上下半年各申報一次）轉上市櫃後，
    quarters 會出現「同一年只有 Q2、Q4 兩筆」——Q2 那筆其實是上半年、Q4 那筆是下半年，不是單季。
    這裡只加標記 period="H1"／"H2"（數值一律不改），讓 App／稽核組近四季 EPS 時認得出來。
    判定：同一年在 quarters 裡剛好是 {2,4} 兩筆（沒有 Q1／Q3）。年度後來補齊 Q1／Q3 時，舊標記拿掉。
    先.一三五-1me（2026-11-07）追加兩條（period_basis 記證據類型）：
      ① month_revenue：Q2 列同年沒有 Q1（或 Q4 列同年沒有 Q3），且該列營收＝當年 1～6 月（7～12 月）月營收加總（±0.5%）、
         又不等於 4～6 月（10～12 月）單季加總 → 標 H1（H2）。月營收對不上就不標。
      ② prior_year_half：當年只有 Q2 一筆、該年 1～6 月月營收查不齊（無法用①證明也無法否證）、
         前一年 Q2／Q4 已是 H1／H2，且營收介於去年上半年的 0.5～2 倍 → 標 H1。
    自身出錯只略過該檔（十二節）。回傳統計。"""
    month_rev = month_rev or {}
    stats = {"tagged_codes": [], "rows_tagged": 0, "untagged_rows": 0, "basis_count": {}}
    for code, s in stocks.items():
        try:
            fin = (s or {}).get("financials") if isinstance(s, dict) else None
            qs = [r for r in ((fin or {}).get("quarters") or []) if isinstance(r, dict)]
            if not qs:
                continue
            mr = month_rev.get(str(code)) or {}
            by_year: dict = {}
            for r in qs:
                by_year.setdefault(r.get("year"), set()).add(r.get("quarter"))
            want: dict = {}  # id(row) -> (period, basis)
            for r in qs:
                y, q = r.get("year"), r.get("quarter")
                if by_year.get(y) == {2, 4} and q in (2, 4):
                    want[id(r)] = ("H1" if q == 2 else "H2", "q2_q4_pair")
            for r in sorted(qs, key=lambda x: (x.get("year") or 0, x.get("quarter") or 0)):
                y, q = r.get("year"), r.get("quarter")
                if id(r) in want or q not in (2, 4) or not isinstance(y, int):
                    continue
                if (q - 1) in by_year.get(y, set()):
                    continue  # 有前一季單季 → 這筆就是單季
                rv = r.get("revenue")
                half = _month_sum(mr, y, range(1, 7) if q == 2 else range(7, 13))
                single = _month_sum(mr, y, range(4, 7) if q == 2 else range(10, 13))
                if half is not None:
                    if _close(rv, half) and not _close(rv, single):
                        want[id(r)] = ("H1" if q == 2 else "H2", "month_revenue")
                    continue
                if q == 2 and by_year.get(y) == {2}:
                    prev = {x.get("quarter"): x for x in qs if x.get("year") == y - 1}
                    p2, p4 = prev.get(2), prev.get(4)
                    if (p2 is not None and p4 is not None and want.get(id(p2), ("",))[0] == "H1"
                            and want.get(id(p4), ("",))[0] == "H2"):
                        pr = p2.get("revenue")
                        try:
                            ok_mag = rv is not None and pr and 0.5 <= rv / pr <= 2.0
                        except TypeError:
                            ok_mag = False
                        if ok_mag:
                            want[id(r)] = ("H1", "prior_year_half")
            hit = False
            for r in qs:
                w = want.get(id(r))
                if w:
                    if r.get("period") != w[0] or r.get("period_basis") != w[1]:
                        if r.get("period") != w[0]:
                            stats["rows_tagged"] += 1
                        r["period"], r["period_basis"] = w
                    stats["basis_count"][w[1]] = stats["basis_count"].get(w[1], 0) + 1
                    hit = True
                elif r.get("period") in ("H1", "H2"):
                    r.pop("period", None)
                    r.pop("period_basis", None)
                    stats["untagged_rows"] += 1
            if hit:
                stats["tagged_codes"].append(str(code))
        except Exception as e:  # 單檔出錯只略過（十二節）
            print(f"[warn] {code} 半年報標記失敗：{e}")
    stats["tagged_codes"].sort()
    return stats


H2_EPS_TOL_ABS = 0.05   # EPS 只存到小數 2 位，絕對誤差下限
H2_EPS_TOL_REL = 0.08   # 相對誤差上限
H2_EPS_MIN_H1 = 0.2     # 上半年 |EPS| 太小時推得的股數不可靠，不判定


H2_EPS_NEIGHBOR_AGREE = 0.10  # 前後相鄰列推得股數彼此相差上限


def _h2_neighbor_shares(qs: list, r: dict, h1: dict):
    """先.一三五-1mv（2026-11-08）：H1 EPS 太小（|EPS|<0.2）推不出股數時，改用相鄰列推股數：
    前一側＝排在該 H2 之前、年份 ≥ 前一年、非 H2、非同年 H1 的最近一列；後一側＝次年第一筆非 H2 列。
    各自需 |EPS|≥0.2 且淨利÷EPS>0；兩側都有時相差須 ≤10%（取平均），只有一側就用那一側；都沒有回 None（不判定）。"""
    y, q = r.get("year"), r.get("quarter")
    if not isinstance(y, int) or not isinstance(q, int):
        return None
    srt = sorted((x for x in qs if isinstance(x.get("year"), int) and isinstance(x.get("quarter"), int)),
                 key=lambda x: (x["year"], x["quarter"]))
    prev = [x for x in srt if (x["year"], x["quarter"]) < (y, q) and x["year"] >= y - 1
            and x.get("period") != "H2" and x is not h1]
    nxt = [x for x in srt if x["year"] == y + 1 and x.get("period") != "H2"]
    cand = []
    for x in (prev[-1] if prev else None, nxt[0] if nxt else None):
        if x is None:
            continue
        e, n = x.get("eps"), x.get("net_income_parent")
        if isinstance(e, (int, float)) and isinstance(n, (int, float)) and abs(e) >= H2_EPS_MIN_H1 and n != 0 and n / e > 0:
            cand.append(n / e)
    if not cand:
        return None
    avg = sum(cand) / len(cand)
    if len(cand) == 2 and abs(cand[0] - cand[1]) / avg > H2_EPS_NEIGHBOR_AGREE:
        return None
    return avg


def fix_h2_cumulative_eps(stocks: dict) -> dict:
    """先.一三五-1ms（2026-11-07）：半年報公司的 H2（Q4）列，歸母淨利是下半年單期，但 EPS 多半是全年累計
    （stock_detail 實測 429 列可判定者，289 列對得上全年累計、39 列對得上下半年單期）。近四季 EPS 用 H2 組 TTM 時會多算半年。
    判定（只在證據充分時才改）：同年有 H1 列，股數＝H1 歸母淨利÷H1 EPS（>0、|H1 EPS|≥0.2），
    H2 EPS 對得上（H1＋H2 淨利）÷股數、對不上 H2 淨利÷股數 → H2 EPS 改成「全年−上半年」，原值存 eps_annual_cum、eps_basis 記
    annual_minus_h1。對不上或無法判定一律不改。每次都重新用證據判定（已改成單期的列對不上全年累計，重跑不會重複扣）。單檔出錯只略過（十二節）。"""
    stats = {"fixed_rows": 0, "fixed_codes": [], "left_unverifiable": 0}
    for code, s in stocks.items():
        try:
            qs = [r for r in ((((s or {}).get("financials") or {}).get("quarters")) or []) if isinstance(r, dict)]
            hit = False
            for r in qs:
                if r.get("period") != "H2":
                    continue
                h1 = next((x for x in qs if x.get("year") == r.get("year") and x.get("period") == "H1"), None)
                vals = (h1 or {}).get("eps"), (h1 or {}).get("net_income_parent"), r.get("eps"), r.get("net_income_parent")
                if h1 is None or any(not isinstance(v, (int, float)) for v in vals):
                    stats["left_unverifiable"] += 1
                    continue
                e1, n1, e2, n2 = vals
                if abs(e1) < H2_EPS_MIN_H1 or n1 == 0 or n1 / e1 <= 0:
                    sh = _h2_neighbor_shares(qs, r, h1)
                    if sh is None:
                        stats["left_unverifiable"] += 1
                        continue
                    basis = "annual_minus_h1_neighbor_shares"
                else:
                    sh = n1 / e1
                    basis = "annual_minus_h1"
                tol = max(H2_EPS_TOL_ABS, H2_EPS_TOL_REL * abs(e2))
                if abs(e2 - (n1 + n2) / sh) < tol and abs(e2 - n2 / sh) > tol:
                    r["eps_annual_cum"] = e2
                    r["eps"] = round(e2 - e1, 2)
                    r["eps_basis"] = basis
                    stats["fixed_rows"] += 1
                    if basis != "annual_minus_h1":
                        stats["fixed_by_neighbor_shares"] = stats.get("fixed_by_neighbor_shares", 0) + 1
                    hit = True
            if hit:
                stats["fixed_codes"].append(str(code))
        except Exception as e:  # 單檔出錯只略過（十二節）
            print(f"[warn] {code} H2 累計 EPS 修正失敗：{e}")
    stats["fixed_codes"].sort()
    return stats


BF_EPS_OUTLIER_MIN_ABS = 0.2   # |EPS| 太小時推得的股數不可靠，不判定
BF_EPS_NEIGHBOR_AGREE = 0.10   # 前後兩季推得股數彼此相差上限
BF_EPS_OUTLIER_DEV = 0.30      # 該季推得股數偏離前後兩季平均的下限


def _implied_shares(r: dict):
    e, n = r.get("eps"), r.get("net_income_parent")
    if not isinstance(e, (int, float)) or not isinstance(n, (int, float)) or abs(e) < BF_EPS_OUTLIER_MIN_ABS or n == 0:
        return None
    sh = n / e
    return sh if sh > 0 else None


def fix_isolated_backfill_eps_outliers(stocks: dict) -> dict:
    """先.一三五-1mu（2026-11-08）：回補檔（FinMind）偶有單季 EPS 與歸母淨利對不上
    （例 6667 2025Q4 EPS 7.01，淨利÷股數約 3.79；用 BWIBBU 本益比反推官方近四季 EPS 14.63，改 3.79 後我方 14.68 對得上）。
    只處理 source=q1_from_backfill、非半年報（period 空）的列；前一季與後一季（連續季度）推得股數（淨利÷EPS）彼此相差 ≤10%，
    而該季推得股數低於兩者平均 >30%（EPS 偏高；EPS 偏低可由特別股股利解釋，不動） → EPS 改成「淨利÷相鄰兩季平均股數」，原值存 eps_raw、eps_basis＝net_div_neighbor_shares。
    持續性的股數基準改變（例 8937 變更面額、EPS 追溯調整，前後季股數本身就不一致）不會觸發，照實保留原值。
    官方列一律不改；已修過的列推得股數已與鄰季一致，重跑不會再改（冪等）。單檔出錯只略過（十二節）。"""
    stats = {"fixed_rows": 0, "fixed": {}}
    for code, s in stocks.items():
        try:
            qs = [r for r in ((((s or {}).get("financials") or {}).get("quarters")) or []) if isinstance(r, dict)]
            idx = {(r.get("year"), r.get("quarter")): r for r in qs if r.get("year") and r.get("quarter")}
            for r in qs:
                if r.get("source") != SRC_Q_FROM_BACKFILL or r.get("period"):
                    continue
                y, q = r.get("year"), r.get("quarter")
                if not y or not q:
                    continue
                k = int(y) * 4 + int(q) - 1
                prev = idx.get(((k - 1) // 4, (k - 1) % 4 + 1))
                nxt = idx.get(((k + 1) // 4, (k + 1) % 4 + 1))
                if prev is None or nxt is None or prev.get("period") or nxt.get("period"):
                    continue
                sp, sn, si = _implied_shares(prev), _implied_shares(nxt), _implied_shares(r)
                n = r.get("net_income_parent")
                if sp is None or sn is None or not isinstance(n, (int, float)) or not isinstance(r.get("eps"), (int, float)):
                    continue
                avg = (sp + sn) / 2
                if abs(sp - sn) / avg > BF_EPS_NEIGHBOR_AGREE:
                    continue
                # 只修「EPS 偏高（推得股數偏低）」：EPS 偏低可由特別股股利正當解釋（例金控 2882／2881 Q2），不動；
                # |EPS| 太小（si 為 None）推不出可靠股數，不判定。
                if si is None or (avg - si) / avg <= BF_EPS_OUTLIER_DEV:
                    continue
                new_eps = round(n / avg, 2)
                r["eps_raw"] = r["eps"]
                r["eps"] = new_eps
                r["eps_basis"] = "net_div_neighbor_shares"
                stats["fixed_rows"] += 1
                stats["fixed"].setdefault(str(code), []).append(f"{y}Q{q} {r['eps_raw']}→{new_eps}")
        except Exception as e:  # 單檔出錯只略過（十二節）
            print(f"[warn] {code} 回補季 EPS 離群修正失敗：{e}")
    return stats


# 先.一三五-1mz（2026-11-08）：官方列（非回補）單季 EPS 孤立離群
OF_EPS_MIN_RESIDUAL = 0.2      # 偏高幅度 |原 EPS − 新 EPS| 太小時，「等於同年較早季 EPS」可能是巧合，不採機制證據
OF_EPS_PRIOR_MATCH_REL = 0.05  # 偏高幅度與同年較早季 EPS（或其加總）相符的容忍（相對）
OF_EPS_PRIOR_MATCH_ABS = 0.03  # 同上（絕對）
OF_EPS_WIDE_TOL = 0.15         # 再往外一季（k±2）推得股數與相鄰兩季平均相差上限（排除整段股數都亂跳的檔，例 6514）


def fix_isolated_official_eps_outliers(stocks: dict, official_map: dict | None = None) -> dict:
    """先.一三五-1mz：官方列（source 不是 q1_from_backfill、非半年報、還沒被其他修正改過）單季 EPS 孤立偏高。
    成因（零外部請求查證）：這些列是早期離散化寫入的「累計 EPS − 同年較早季」，當時較早季 EPS 是 None，
    舊版 `or 0` 把它當 0 少減一季（先.一二五-1 已修產生端，但已寫入的舊列沒重算）——
    例 3583 2025Q4 7.77＝真 Q4 約 4.10＋Q3 3.66；2072 2025Q2 5.21＝真 Q2 約 2.71＋Q1 2.49；2729 2024Q4 4.34＝約 1.45＋Q3 2.89。
    判定比照 fix_isolated_backfill_eps_outliers（前後季推得股數彼此差 ≤10%、該季低於平均 >30%），另加：
    ① 再外一季（k±2，非半年報、可推股數者至少一筆）也要在平均 ±15% 內；
    ② 需有證據才改：(a) 偏高幅度（≥0.2）等於同年某些較早季 EPS 加總（少減一季的機制證據），或
       (b) 該列在近四季內，官方本益比反推近四季 EPS 用新值對得上、原值對不上（容忍同 先.一三五-1mx）；
       在近四季內而官方數字對得上原值 → 不改。沒有證據 → 照實列 left_unverified，不改。
    EPS 改成淨利÷相鄰兩季平均股數，原值存 eps_raw、eps_basis＝official_net_div_neighbor_shares、eps_fix_evidence 記證據。
    只修偏高（偏低可由特別股股利解釋，例金控 Q2）；重跑冪等（有 eps_basis／eps_raw 的列不動）。單檔出錯只略過（十二節）。"""
    import itertools
    stats = {"fixed_rows": 0, "fixed": {}, "left_unverified": []}
    if official_map is None:
        official_map = load_official_ttm_eps_map()

    def match_official(x, off):
        return abs(x - off) <= max(SHIFT_MATCH_ABS, SHIFT_MATCH_REL * abs(off))

    for code, s in stocks.items():
        try:
            qs = [r for r in ((((s or {}).get("financials") or {}).get("quarters")) or [])
                  if isinstance(r, dict) and r.get("year") and r.get("quarter")]
            idx = {(int(r["year"]), int(r["quarter"])): r for r in qs}

            def at(k):
                return idx.get((k // 4, k % 4 + 1))
            srt = sorted(qs, key=lambda r: (int(r["year"]), int(r["quarter"])))
            last4 = srt[-4:]
            ks4 = [int(r["year"]) * 4 + int(r["quarter"]) for r in last4]
            last4_ok = (len(last4) == 4 and ks4 == list(range(ks4[0], ks4[0] + 4))
                        and not any(r.get("period") for r in last4)
                        and all(isinstance(r.get("eps"), (int, float)) for r in last4))
            for r in qs:
                if r.get("source") == SRC_Q_FROM_BACKFILL or r.get("period") or r.get("eps_basis") or "eps_raw" in r:
                    continue
                y, q = int(r["year"]), int(r["quarter"])
                k = y * 4 + q - 1
                prev, nxt = at(k - 1), at(k + 1)
                if prev is None or nxt is None or prev.get("period") or nxt.get("period"):
                    continue
                sp, sn, si = _implied_shares(prev), _implied_shares(nxt), _implied_shares(r)
                n, e = r.get("net_income_parent"), r.get("eps")
                if sp is None or sn is None or si is None or not isinstance(n, (int, float)) or not isinstance(e, (int, float)):
                    continue
                avg = (sp + sn) / 2
                if abs(sp - sn) / avg > BF_EPS_NEIGHBOR_AGREE or (avg - si) / avg <= BF_EPS_OUTLIER_DEV:
                    continue
                label = f"{code} {y}Q{q}"
                wide = [_implied_shares(w) for w in (at(k - 2), at(k + 2)) if w is not None and not w.get("period")]
                wide = [w for w in wide if w is not None]
                if not wide or any(abs(w - avg) / avg > OF_EPS_WIDE_TOL for w in wide):
                    stats["left_unverified"].append(f"{label} eps={e}：再外一季股數不一致或缺")
                    continue
                new_eps = round(n / avg, 2)
                residual = e - new_eps
                evidence = []
                if abs(residual) >= OF_EPS_PRIOR_MATCH_ABS and abs(residual) >= OF_EPS_MIN_RESIDUAL:
                    same = [(qq, idx[(y, qq)]["eps"]) for qq in range(1, q)
                            if (y, qq) in idx and isinstance(idx[(y, qq)].get("eps"), (int, float))]
                    for L in range(1, len(same) + 1):
                        hit = next((c for c in itertools.combinations(same, L)
                                    if abs(sum(x for _, x in c) - residual) <= max(OF_EPS_PRIOR_MATCH_ABS, OF_EPS_PRIOR_MATCH_REL * abs(residual))), None)
                        if hit:
                            evidence.append("cum_missed_prior:" + "+".join(f"Q{qq}" for qq, _ in hit))
                            break
                off = official_map.get(str(code))
                ttm_note = None
                if last4_ok and r in last4 and isinstance(off, (int, float)):
                    ttm_old = round(sum(x["eps"] for x in last4), 2)
                    ttm_new = round(ttm_old - e + new_eps, 2)
                    if match_official(ttm_old, off):
                        stats["left_unverified"].append(f"{label} eps={e}：官方近四季 {off} 對得上原值 {ttm_old}，不改")
                        continue
                    if match_official(ttm_new, off):
                        evidence.append("official_ttm")
                        ttm_note = {"official": off, "ttm_old": ttm_old, "ttm_new": ttm_new}
                if not evidence:
                    stats["left_unverified"].append(f"{label} eps={e}（推估 {new_eps}）：無機制證據、官方近四季也無法核對")
                    continue
                r["eps_raw"] = e
                r["eps"] = new_eps
                r["eps_basis"] = "official_net_div_neighbor_shares"
                r["eps_fix_evidence"] = evidence + ([f"official_ttm {ttm_note['ttm_old']}→{ttm_note['ttm_new']} vs {ttm_note['official']}"] if ttm_note else [])
                stats["fixed_rows"] += 1
                stats["fixed"].setdefault(str(code), []).append(f"{y}Q{q} {e}→{new_eps}（{'、'.join(evidence)}）")
        except Exception as ex:  # 單檔出錯只略過（十二節）
            print(f"[warn] {code} 官方列 EPS 離群修正失敗：{ex}")
    return stats

# 先.一三五-1mx（2026-11-08）：股數基準持續跳變（變更面額／股票分割、EPS 追溯調整）
SHIFT_MIN_ABS_EPS = 0.05     # |EPS| 太小推得股數不可靠，不當判定點
SHIFT_RATIO_HI = 1.5         # 新／舊推得股數倍數 ≥1.5 或 ≤0.67 才算跳變
SHIFT_RATIO_LO = 0.67
SHIFT_LEVEL_TOL = 0.15       # 同一水準內各季推得股數與中位數相差上限
SHIFT_MIN_NEW_POINTS = 2     # 跳變後至少 2 季都在新水準（排除金控 Q2 特別股股利這類單季偏離）
SHIFT_MIN_OLD_POINTS = 2     # 跳變前也至少 2 季在舊水準（排除單季孤立離群被誤認成基準改變）
SHIFT_MATCH_REL = 0.10       # 對官方近四季 EPS 的容忍（相對）
SHIFT_MATCH_ABS = 0.03       # 對官方近四季 EPS 的容忍（絕對，EPS 很小時用）
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
QUOTES_ALL_TW_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _shift_implied_shares(r: dict):
    e, n = r.get("eps"), r.get("net_income_parent")
    if not isinstance(e, (int, float)) or not isinstance(n, (int, float)) or abs(e) < SHIFT_MIN_ABS_EPS or n == 0:
        return None
    sh = n / e
    return sh if sh > 0 else None


def load_official_ttm_eps_map(fund_path: Path | None = None, quotes_path: Path | None = None) -> dict:
    """零外部請求：官方本益比（fundamentals.json ratios.per，來自 BWIBBU／TPEx 本益比）× 同日收盤（quotes_all_tw.json）
    反推官方近四季 EPS＝收盤÷本益比。日期不同或缺值就不收（不拿不同日的價格硬湊）。讀不到檔回空 dict。"""
    out = {}
    try:
        fund = json.loads((fund_path or FUNDAMENTALS_PATH).read_text(encoding="utf-8")).get("fundamentals") or {}
        quotes = json.loads((quotes_path or QUOTES_ALL_TW_PATH).read_text(encoding="utf-8")).get("quotes") or {}
    except Exception as e:  # 十二節：讀不到只警告，回空（不做任何調整）
        print(f"[warn] 官方本益比／收盤讀取失敗，股數基準追溯調整本次略過：{e}")
        return out
    for code, f in fund.items():
        try:
            ra = (f or {}).get("ratios") or {}
            per, q = ra.get("per"), quotes.get(code) or {}
            close = q.get("close")
            if not isinstance(per, (int, float)) or per <= 0 or not isinstance(close, (int, float)) or close <= 0:
                continue
            if not ra.get("date") or ra.get("date") != (q.get("as_of") or q.get("date")):
                continue
            out[str(code)] = round(close / per, 4)
        except Exception as e:
            print(f"[warn] {code} 官方近四季 EPS 反推失敗：{e}")
    return out


def detect_share_base_shift(quarters: list) -> dict | None:
    """找「最後一次」持續性的股數基準跳變：相鄰判定點推得股數（淨利÷EPS）倍數 ≥1.5 或 ≤0.67，
    跳變後至少 2 個判定點都在新水準（±15%）、跳變前也至少 2 個判定點在舊水準（±15%，連續區段）。
    回傳 break_at、factor（新÷舊）、old_rows（要追溯調整的舊基準季 (year, quarter)：從跳變往回、
    推得股數在舊水準或 |EPS| 太小無法判定的連續列）。沒有就回 None。不改資料。"""
    qs = sorted([r for r in (quarters or []) if isinstance(r, dict) and r.get("year") and r.get("quarter")],
                key=lambda r: (int(r["year"]), int(r["quarter"])))
    pts = [(i, _shift_implied_shares(r)) for i, r in enumerate(qs)]
    pts = [(i, s) for i, s in pts if s is not None]
    if len(pts) < SHIFT_MIN_NEW_POINTS + 1:
        return None
    for j in range(len(pts) - SHIFT_MIN_NEW_POINTS, 0, -1):
        new_vals = [s for _, s in pts[j:]]
        new_med = _median(new_vals)
        if any(abs(s - new_med) / new_med > SHIFT_LEVEL_TOL for s in new_vals):
            continue
        prev_s = pts[j - 1][1]
        ratio = new_med / prev_s
        if SHIFT_RATIO_LO < ratio < SHIFT_RATIO_HI:
            continue
        old_vals = []
        for _, s in reversed(pts[:j]):
            if abs(s - prev_s) / prev_s > SHIFT_LEVEL_TOL:
                break
            old_vals.append(s)
        if len(old_vals) < SHIFT_MIN_OLD_POINTS:  # 舊水準只有 1 點＝孤立離群（例 2329／3583 官方 2025Q4），不是基準改變
            continue
        old_med = _median(old_vals)
        factor = new_med / old_med
        if SHIFT_RATIO_LO < factor < SHIFT_RATIO_HI:
            continue
        bi = pts[j][0]
        old_rows = []
        for r in reversed(qs[:bi]):
            if not isinstance(r.get("eps"), (int, float)):
                break
            s = _shift_implied_shares(r)
            if s is not None and abs(s - old_med) / old_med > SHIFT_LEVEL_TOL:
                break
            old_rows.append((int(r["year"]), int(r["quarter"])))
        if not old_rows:
            return None
        b = qs[bi]
        return {"break_at": f"{b['year']}Q{b['quarter']}", "factor": factor, "old_shares": old_med,
                "new_shares": new_med, "old_rows": old_rows, "new_points": len(new_vals), "old_points": len(old_vals)}
    return None


def verify_share_base_shift(quarters: list, shift: dict, official_ttm) -> dict:
    """用官方近四季 EPS（收盤÷本益比）核對：近四季（需連續、非半年報）用原值加總 vs 舊基準季÷倍數後加總，
    只有「調整後對得上、原值對不上」才回 status=matched；其他照實回 old_matches／neither／no_official／outside_window／not_consecutive。"""
    qs = sorted([r for r in (quarters or []) if isinstance(r, dict) and r.get("year") and r.get("quarter")],
                key=lambda r: (int(r["year"]), int(r["quarter"])))
    last4 = qs[-4:]
    if len(last4) < 4 or any(r.get("period") for r in last4) or any(not isinstance(r.get("eps"), (int, float)) for r in last4):
        return {"status": "not_consecutive"}
    ks = [int(r["year"]) * 4 + int(r["quarter"]) for r in last4]
    if ks != list(range(ks[0], ks[0] + 4)):
        return {"status": "not_consecutive"}
    old = set(tuple(x) for x in shift["old_rows"])
    in_win = [r for r in last4 if (int(r["year"]), int(r["quarter"])) in old]
    ttm_old = round(sum(r["eps"] for r in last4), 2)
    # 已被其他修正改過 EPS 的列（有 eps_basis）實際不會調整，核對時也照原值算，跟 restate 行為一致
    ttm_new = round(sum(round(r["eps"] / shift["factor"], 2)
                        if (int(r["year"]), int(r["quarter"])) in old and not r.get("eps_basis") else r["eps"]
                        for r in last4), 2)
    res = {"ttm_old": ttm_old, "ttm_restated": ttm_new}
    if not in_win:
        res["status"] = "outside_window"
        return res
    if not isinstance(official_ttm, (int, float)):
        res["status"] = "no_official"
        return res

    def ok(x):
        return abs(x - official_ttm) <= max(SHIFT_MATCH_ABS, SHIFT_MATCH_REL * abs(official_ttm))

    res["status"] = "matched" if ok(ttm_new) and not ok(ttm_old) else ("old_matches" if ok(ttm_old) else "neither")
    return res


def restate_share_base_shift(stocks: dict, official_map: dict | None = None) -> dict:
    """先.一三五-1mx：近四季 EPS 跨越股數基準改變（例 8937 合騏*：2025 各季約 1 億股、2026 起約 4.2 億股，
    官方本益比反推近四季 EPS 0.06、我方混用新舊基準 0.94）。偵測到持續跳變、且用官方近四季 EPS 證實
    「舊季 EPS÷倍數」才對得上（status=matched）時，把舊基準季 EPS 追溯調整成新基準：原值存 eps_pre_restate、
    eps＝round(原值÷倍數, 2)、eps_basis＝restated_share_base、restate_factor 記倍數。只改 EPS，不改淨利。
    已被其他修正改過 EPS 的列（有 eps_basis，例 6667 的 net_div_neighbor_shares）不動。
    對不上的只記錄。調整後舊季推得股數已在新水準，重跑不會再偵測到（冪等）。單檔出錯只略過（十二節）。"""
    if official_map is None:
        official_map = load_official_ttm_eps_map()
    stats = {"detected": 0, "restated_codes": {}, "restated_rows": 0, "not_restated": {}, "skipped_rows_with_other_basis": [],
             "restated_rows_present": 0, "errors": []}
    for code, s in stocks.items():
        try:
            qs = [r for r in ((((s or {}).get("financials") or {}).get("quarters")) or []) if isinstance(r, dict)]
            stats["restated_rows_present"] += sum(1 for r in qs if r.get("eps_basis") == "restated_share_base")
            sh = detect_share_base_shift(qs)
            if not sh:
                continue
            stats["detected"] += 1
            v = verify_share_base_shift(qs, sh, official_map.get(str(code)))
            if v["status"] != "matched":
                stats["not_restated"][str(code)] = {"break_at": sh["break_at"], "factor": round(sh["factor"], 3),
                                                    "official_ttm": official_map.get(str(code)), **v}
                continue
            old = set(tuple(x) for x in sh["old_rows"])
            changed = []
            for r in qs:
                if (int(r.get("year") or 0), int(r.get("quarter") or 0)) not in old:
                    continue
                if r.get("eps_basis"):
                    stats["skipped_rows_with_other_basis"].append(f"{code} {r['year']}Q{r['quarter']} {r['eps_basis']}")
                    continue
                r["eps_pre_restate"] = r["eps"]
                r["eps"] = round(r["eps"] / sh["factor"], 2)
                r["eps_basis"] = "restated_share_base"
                r["restate_factor"] = round(sh["factor"], 4)
                changed.append(f"{r['year']}Q{r['quarter']} {r['eps_pre_restate']}→{r['eps']}")
            if changed:
                stats["restated_rows"] += len(changed)
                stats["restated_rows_present"] += len(changed)
                stats["restated_codes"][str(code)] = {"break_at": sh["break_at"], "factor": round(sh["factor"], 3),
                                                      "official_ttm": official_map.get(str(code)), "ttm_before": v["ttm_old"],
                                                      "ttm_after": v["ttm_restated"], "rows": changed}
        except Exception as e:  # 單檔出錯只略過（十二節）
            print(f"[warn] {code} 股數基準追溯調整失敗：{e}")
            stats["errors"].append(f"{code}: {e}")
    return stats


SHARES_IMPLIED_DEV = 0.30     # 股本÷10 與推得股數相差超過 30% 才改用推得股數
SHARES_IMPLIED_AGREE = 0.15   # 用來推股數的兩季彼此相差上限（排除金控 Q2 特別股股利這類單季偏離）


def fix_shares_by_implied_eps(stocks: dict) -> dict:
    """先.一三五-1my（2026-11-08）：`shares_outstanding_approx`＝普通股股本(仟元)÷10 假設每股面額 10 元，
    對面額非 10 元的股票（櫃買名稱帶 *，例 8937 合騏*：股本÷10＝約 1.08 億股，實際約 4.2 億股）會錯。
    取最近兩個可判定季（|EPS|≥0.05、淨利÷EPS 為正）推得股數（仟股），兩季彼此相差 ≤15% 時取平均；
    比股本÷10 多 >30%（面額小於 10 元）→ 改用推得股數；比股本÷10 少 >30% 只記錄不改，`shares_basis=implied_from_eps`，原值存 `shares_from_capital_div10`。
    回到 30% 內就還原成股本÷10 並拿掉標記。每次以 shares_from_capital_div10（若有）為基準重判，冪等。單檔出錯只略過（十二節）。"""
    stats = {"changed": {}, "reverted": [], "implied_present": 0, "unverifiable_large_gap": [], "errors": []}
    for code, s in stocks.items():
        try:
            fin = (s or {}).get("financials") or {}
            base = fin.get("shares_from_capital_div10") if fin.get("shares_basis") == "implied_from_eps" else fin.get("shares_outstanding_approx")
            if not isinstance(base, (int, float)) or base <= 0:
                continue
            qs = sorted([r for r in (fin.get("quarters") or []) if isinstance(r, dict) and r.get("year") and r.get("quarter")],
                        key=lambda r: (int(r["year"]), int(r["quarter"])))
            pts = [x for x in (_shift_implied_shares(r) for r in reversed(qs[-4:])) if x is not None][:2]
            implied_k = None
            if len(pts) == 2 and abs(pts[0] - pts[1]) / ((pts[0] + pts[1]) / 2) <= SHARES_IMPLIED_AGREE:
                implied_k = round((pts[0] + pts[1]) / 2 / 1000, 0)  # 股→仟股
            if implied_k and (base - implied_k) / base > SHARES_IMPLIED_DEV:
                # 推得股數比股本÷10 少 >30%：面額大於 10 元極罕見，多半是股本欄位或加權股數差異，只記錄不改
                stats["unverifiable_large_gap"].append(f"{code} 股本÷10={base:.0f} 推得={implied_k:.0f}")
            if implied_k and (implied_k - base) / base > SHARES_IMPLIED_DEV:
                if fin.get("shares_outstanding_approx") != implied_k or fin.get("shares_basis") != "implied_from_eps":
                    stats["changed"][str(code)] = {"capital_div10_k": base, "implied_k": implied_k, "ratio": round(implied_k / base, 3)}
                fin["shares_from_capital_div10"] = base
                fin["shares_outstanding_approx"] = implied_k
                fin["shares_basis"] = "implied_from_eps"
                stats["implied_present"] += 1
            elif fin.get("shares_basis") == "implied_from_eps":
                if implied_k is None:  # 推不出股數就維持上次判定，不來回切換
                    stats["implied_present"] += 1
                    continue
                fin["shares_outstanding_approx"] = base
                fin.pop("shares_basis", None)
                fin.pop("shares_from_capital_div10", None)
                stats["reverted"].append(str(code))
        except Exception as e:  # 十二節
            print(f"[warn] {code} 推得股數修正失敗：{e}")
            stats["errors"].append(f"{code}: {e}")
    return stats


def _shares_meta(st: dict, mode: str) -> dict:
    return {"note": "shares_outstanding_approx（仟股）原為股本÷10（假設面額 10 元）；最近兩季淨利÷EPS 推得股數（兩季相差 ≤15%）比之多 >30%（面額小於 10 元）時改用推得股數、少 >30% 只記錄，"
                    "shares_basis=implied_from_eps、原值存 shares_from_capital_div10（先.一三五-1my）",
            "changed_this_run": st["changed"], "reverted_this_run": st["reverted"], "implied_present": st["implied_present"],
            "lower_than_capital_not_changed": st["unverifiable_large_gap"],
            "errors": st["errors"], "generated_at": datetime.now(TW_TZ).isoformat(), "mode": mode}


def _share_base_meta(st: dict, mode: str) -> dict:
    return {"note": "近四季 EPS 跨越股數基準持續跳變（推得股數倍數 ≥1.5 或 ≤0.67、跳變後 ≥2 季在新水準）且以官方本益比×收盤反推的近四季 EPS 證實"
                    "「舊季 EPS÷倍數」才對得上時，舊基準季 EPS 追溯調整成新基準，原值存 eps_pre_restate、eps_basis=restated_share_base；只改 EPS 不改淨利；"
                    "對不上的列在 not_restated 只記錄（先.一三五-1mx）",
            "detected": st["detected"], "restated_this_run": len(st["restated_codes"]), "restated_rows_this_run": st["restated_rows"],
            "restated_rows_present": st["restated_rows_present"], "restated_codes": st["restated_codes"],
            "not_restated": st["not_restated"], "skipped_rows_with_other_basis": st["skipped_rows_with_other_basis"],
            "errors": st["errors"], "generated_at": datetime.now(TW_TZ).isoformat(), "mode": mode}


def offline_merge_backfill() -> None:
    """零外部請求：只讀既有 stock_detail.json＋financials_backfill.json，併回補季後寫回（本機重產／驗證用）。"""
    payload = load_existing()
    stocks = payload.setdefault("stocks", {})
    st = merge_backfill_display_quarters(stocks, load_backfill())
    payload.setdefault("meta", {})["financials_backfill_display_merge"] = {
        "note": "官方 quarters 沒有的季度取自 financials_backfill.json（FinMind，App 顯示用），標 source=q1_from_backfill；官方同季優先（先.一三五-1lw）",
        "merged_count": len(st["merged_codes"]), "rows_added": st["rows_added"], "rejected": st["rejected"],
        "eps_mismatch_passed": st["eps_mismatch_passed"],
        "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "offline"}
    try:
        _r = recompute_roe_after_backfill_merge(stocks, _codes_with_backfill_quarters(stocks))
        payload["meta"]["roe_recomputed_after_backfill_merge"] = {
            "note": "併入回補季的檔用合併後近四季重算 ROE；最後一季須等於 latest_cum、四季須連續，否則 None（先.一三五-1md）",
            "recomputed_count": len(_r["recomputed"]), "set_none_count": len(_r["set_none"]), "errors": _r["errors"]}
    except Exception as e:  # 十二節：重算自己出錯只警告
        print(f"[warn] 回補季併入後 ROE 重算失敗：{e}")
    # 先.一三五-1mk：跟每日路徑同順序——ROE 重算 → 半年報標記 → ROE 連續性清理，各自 try（十二節）
    try:
        _hy = tag_half_year_periods(stocks, load_month_revenue_map())
        payload["meta"]["financials_half_year_period"] = {
            "note": "同一年 quarters 只有 Q2／Q4 兩筆（半年報公司）時，Q2 標 period=H1（上半年）、Q4 標 period=H2（下半年），數值不改（先.一三五-1mb）；"
                    "另以月營收證明（營收＝半年月營收加總）或前一年已是半年報＋今年只有 Q2 標記，period_basis 記證據類型（先.一三五-1me）",
            "tagged_count": len(_hy["tagged_codes"]), "tagged_codes": _hy["tagged_codes"], "basis_count": _hy["basis_count"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "offline"}
    except Exception as e:
        print(f"[warn] 半年報標記失敗：{e}")
    try:  # 先.一三五-1ms：H2 列 EPS 是全年累計時改成全年−上半年；自身失敗只警告（十二節）
        _h2 = fix_h2_cumulative_eps(stocks)
        payload["meta"]["financials_h2_eps_fix"] = {
            "note": "H2 列 EPS 對得上全年累計、對不上下半年單期（以 H1 淨利÷EPS 推股數；H1 EPS 太小改用相鄰列推股數，eps_basis 記 annual_minus_h1_neighbor_shares）時，改成全年−上半年，原值存 eps_annual_cum（先.一三五-1ms／1mv）",
            "fixed_rows": _h2["fixed_rows"], "fixed_by_neighbor_shares": _h2.get("fixed_by_neighbor_shares", 0), "fixed_codes": _h2["fixed_codes"], "left_unverifiable": _h2["left_unverifiable"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "offline"}
    except Exception as e:
        print(f"[warn] H2 累計 EPS 修正失敗：{e}")
    try:  # 先.一三五-1mu：回補季單季 EPS 與淨利對不上（孤立離群）時改用相鄰季股數；自身失敗只警告（十二節）
        _bo = fix_isolated_backfill_eps_outliers(stocks)
        payload["meta"]["financials_backfill_eps_outlier_fix"] = {
            "note": "回補季 EPS 推得股數低於前後兩季（兩季彼此一致）平均 >30% 時，EPS 改成淨利÷相鄰季平均股數，原值存 eps_raw（先.一三五-1mu）",
            "fixed_rows": _bo["fixed_rows"], "fixed": _bo["fixed"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "offline"}
    except Exception as e:
        print(f"[warn] 回補季 EPS 離群修正失敗：{e}")
    try:  # 先.一三五-1mz：官方列單季 EPS 孤立偏高（舊離散化少減一季）且有證據時改用相鄰季股數；自身失敗只警告（十二節）
        _of = fix_isolated_official_eps_outliers(stocks)
        payload["meta"]["financials_official_eps_outlier_fix"] = {
            "note": "官方列 EPS 推得股數低於前後兩季（兩季彼此一致、再外一季也一致）平均 >30%，且偏高幅度等於同年較早季 EPS（舊離散化少減一季）"
                    "或官方本益比反推近四季 EPS 證實時，EPS 改成淨利÷相鄰季平均股數，原值存 eps_raw（先.一三五-1mz）",
            "fixed_rows": _of["fixed_rows"], "fixed": _of["fixed"], "left_unverified": _of["left_unverified"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "offline"}
    except Exception as e:
        print(f"[warn] 官方列 EPS 離群修正失敗：{e}")
    try:  # 先.一三五-1mx：股數基準持續跳變且官方近四季 EPS 證實時，舊季 EPS 追溯調整；自身失敗只警告（十二節）
        payload["meta"]["financials_share_base_restate"] = _share_base_meta(restate_share_base_shift(stocks), "offline")
    except Exception as e:
        print(f"[warn] 股數基準追溯調整失敗：{e}")
    try:  # 先.一三五-1my：面額非 10 元時股本÷10 推的股數會錯，改用推得股數；自身失敗只警告（十二節）
        payload["meta"]["financials_shares_implied_fix"] = _shares_meta(fix_shares_by_implied_eps(stocks), "offline")
    except Exception as e:
        print(f"[warn] 推得股數修正失敗：{e}")
    try:
        payload["meta"]["roe_cleared_nonconsecutive_codes"] = clear_stale_nonconsecutive_roe(stocks)
    except Exception as e:
        print(f"[warn] ROE 連續性複查失敗：{e}")
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"離線併入回補季：{len(st['merged_codes'])} 檔、{st['rows_added']} 季；拒絕 {len(st['rejected'])} 檔")


def main():
    payload = load_existing()
    stocks = payload.setdefault("stocks", {})

    errors = []
    income_updated = 0
    skipped_no_baseline = 0
    skipped_no_baseline_codes = []  # 先.一二一-2：計數旁存代號清單，BACKLOG「979 檔缺 Q1 基準」才能逐檔對
    backfill_used_codes, backfill_rejected, dropped_cum_as_single = [], {}, []
    try:
        income = fetch_income()
        equity = fetch_balance()
        backfill = None
        for code, cum in income.items():
            entry = stocks.setdefault(code, {})
            fin = entry.setdefault("financials", {})
            existing_quarters = fin.get("quarters", [])
            discrete = discretize_quarter(existing_quarters, cum)
            if discrete is not None:
                # 基準季若是回補檔來的，還原出的單季也沿用標記（之後每輪都走這條，標記才不會掉）
                if any(r.get("year") == cum["year"] and r.get("quarter", 0) < cum["quarter"]
                       and r.get("source") == SRC_Q_FROM_BACKFILL for r in existing_quarters):
                    discrete["source"] = SRC_RESTORED_WITH_BACKFILL
                fin["quarters"] = merge_quarters(existing_quarters, discrete)
            else:
                if backfill is None:
                    backfill = load_backfill()
                rows, why = (None, "回補檔無此代號")
                if str(code) in backfill:
                    try:
                        rows, why = restore_with_backfill(existing_quarters, cum, backfill[str(code)])
                    except Exception as e:  # 回補路徑出錯只當沒補到，不影響其他檔
                        rows, why = None, f"回補還原失敗：{e}"
                if rows is None:
                    skipped_no_baseline += 1
                    skipped_no_baseline_codes.append(str(code))
                    if str(code) in backfill:
                        backfill_rejected[str(code)] = why
                    # [自行裁量] 2026-08-27 修正前那一輪把「累計數」當單季、且單位仟元寫進同一季（先.一二三-1 157 檔）。
                    # 還原不了時，至少把這筆已知錯值拿掉（寧可空，不顯示錯的）：同季、同年沒有較早季度、營收等於本次累計數。
                    same = [r for r in existing_quarters if (r.get("year"), r.get("quarter")) == (cum["year"], cum["quarter"])]
                    no_prior = not any(r.get("year") == cum["year"] and r.get("quarter", 0) < cum["quarter"] for r in existing_quarters)
                    if cum["quarter"] > 1 and same and no_prior and cum.get("revenue_cum"):
                        rv = same[0].get("revenue") or 0
                        if any(abs(rv * k - cum["revenue_cum"]) <= 0.005 * abs(cum["revenue_cum"]) for k in (1, 1000)):
                            fin["quarters"] = [r for r in existing_quarters if r not in same]
                            dropped_cum_as_single.append(str(code))
                    continue
                qs = existing_quarters
                for r in rows:
                    qs = merge_quarters(qs, r)
                fin["quarters"] = qs
                backfill_used_codes.append(str(code))
            bal = equity.get(code) or {}
            eq = bal.get("equity")
            fin["equity_parent_latest"] = eq
            fin["roe_ttm_pct"] = compute_roe_ttm(fin["quarters"], eq * 1000 if eq else None)  # 權益仟元→元（2026-10-11 修正）
            fin["source"] = "t187ap06_L_ci"
            fin["industry_format"] = "上市一般業"
            fin["latest_cum"] = dict(cum, source="t187ap06_L_ci", industry="上市一般業")
            capital = bal.get("common_stock_capital")
            fin["shares_outstanding_approx"] = round(capital / 10, 0) if capital else None
            fin.pop("shares_basis", None)  # 先.一三五-1my：同上，重寫後交給 fix_shares_by_implied_eps 重判
            fin.pop("shares_from_capital_div10", None)
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
    payload["meta"]["financials_skipped_no_baseline_codes"] = sorted(set(skipped_no_baseline_codes))
    # 先.一二五-1：缺基準改用回補檔的結果（App 顯示用途；研究端回測不得讀這些標記的季度）
    payload["meta"]["financials_baseline_from_backfill"] = {
        "note": f"同年較早季度缺時取 financials_backfill.json（FinMind，元）當基準；基準季標 source={SRC_Q_FROM_BACKFILL}、"
                f"還原季標 source={SRC_RESTORED_WITH_BACKFILL}；與回補檔同季營收／歸母淨利差 >{BACKFILL_MAX_DIFF:.0%} 或 EPS 差 >{BACKFILL_EPS_ABS_TOL} 不寫",
        "used_this_run_codes": sorted(set(backfill_used_codes)),
        # 全檔目前帶回補標記的代號（第一次補上之後，下一輪起走一般路徑，本輪清單會是空的，所以另算全檔）
        "tagged_codes": sorted(c for c, s in stocks.items()
                               if any(r.get("source") in (SRC_Q_FROM_BACKFILL, SRC_RESTORED_WITH_BACKFILL)
                                      for r in ((s.get("financials") or {}).get("quarters") or []))),
        "rejected": dict(sorted(backfill_rejected.items())),
        "dropped_cumulative_as_single_codes": sorted(set(dropped_cum_as_single)),
    }
    # 先.一三五-1lw：官方 quarters 沒有的季度取回補檔補上（App 顯示用）；自身失敗只警告（十二節）
    try:
        _st = merge_backfill_display_quarters(stocks, load_backfill())
        payload["meta"]["financials_backfill_display_merge"] = {
            "note": "官方 quarters 沒有的季度取自 financials_backfill.json（FinMind，App 顯示用），標 source=q1_from_backfill；官方同季優先（先.一三五-1lw）",
            "merged_count": len(_st["merged_codes"]), "rows_added": _st["rows_added"], "rejected": _st["rejected"],
            "eps_mismatch_passed": _st["eps_mismatch_passed"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "daily"}
    except Exception as e:
        print(f"[warn] 回補季併入失敗：{e}")
        errors.append(f"backfill_display_merge: {e}")
    # 先.一三五-1md：併入回補季後用合併後近四季重算 ROE；自身失敗只警告（十二節）
    try:
        _r = recompute_roe_after_backfill_merge(stocks, _codes_with_backfill_quarters(stocks))
        payload["meta"]["roe_recomputed_after_backfill_merge"] = {
            "note": "併入回補季的檔用合併後近四季重算 ROE；最後一季須等於 latest_cum、四季須連續，否則 None（先.一三五-1md）",
            "recomputed_count": len(_r["recomputed"]), "set_none_count": len(_r["set_none"]), "errors": _r["errors"]}
    except Exception as e:
        print(f"[warn] 回補季併入後 ROE 重算失敗：{e}")
        errors.append(f"roe_recompute_after_merge: {e}")
    # 先.一三五-1mb：半年報列標 period=H1/H2（不改數值）；自身失敗只警告（十二節）
    try:
        _hy = tag_half_year_periods(stocks, load_month_revenue_map())
        payload["meta"]["financials_half_year_period"] = {
            "note": "同一年 quarters 只有 Q2／Q4 兩筆（半年報公司）時，Q2 標 period=H1（上半年）、Q4 標 period=H2（下半年），數值不改（先.一三五-1mb）；"
                    "另以月營收證明（營收＝半年月營收加總）或前一年已是半年報＋今年只有 Q2 標記，period_basis 記證據類型（先.一三五-1me）",
            "tagged_count": len(_hy["tagged_codes"]), "tagged_codes": _hy["tagged_codes"], "basis_count": _hy["basis_count"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "daily"}
    except Exception as e:
        print(f"[warn] 半年報標記失敗：{e}")
        errors.append(f"half_year_period: {e}")
    try:  # 先.一三五-1ms：H2 列 EPS 是全年累計時改成全年−上半年；自身失敗只警告（十二節）
        _h2 = fix_h2_cumulative_eps(stocks)
        payload["meta"]["financials_h2_eps_fix"] = {
            "note": "H2 列 EPS 對得上全年累計、對不上下半年單期（以 H1 淨利÷EPS 推股數；H1 EPS 太小改用相鄰列推股數，eps_basis 記 annual_minus_h1_neighbor_shares）時，改成全年−上半年，原值存 eps_annual_cum（先.一三五-1ms／1mv）",
            "fixed_rows": _h2["fixed_rows"], "fixed_by_neighbor_shares": _h2.get("fixed_by_neighbor_shares", 0), "fixed_codes": _h2["fixed_codes"], "left_unverifiable": _h2["left_unverifiable"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "daily"}
    except Exception as e:
        print(f"[warn] H2 累計 EPS 修正失敗：{e}")
        errors.append(f"h2_eps_fix: {e}")
    try:  # 先.一三五-1mu：回補季單季 EPS 與淨利對不上（孤立離群）時改用相鄰季股數；自身失敗只警告（十二節）
        _bo = fix_isolated_backfill_eps_outliers(stocks)
        payload["meta"]["financials_backfill_eps_outlier_fix"] = {
            "note": "回補季 EPS 推得股數低於前後兩季（兩季彼此一致）平均 >30% 時，EPS 改成淨利÷相鄰季平均股數，原值存 eps_raw（先.一三五-1mu）",
            "fixed_rows": _bo["fixed_rows"], "fixed": _bo["fixed"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "daily"}
    except Exception as e:
        print(f"[warn] 回補季 EPS 離群修正失敗：{e}")
        errors.append(f"backfill_eps_outlier_fix: {e}")
    try:  # 先.一三五-1mz：官方列單季 EPS 孤立偏高（舊離散化少減一季）且有證據時改用相鄰季股數；自身失敗只警告（十二節）
        _of = fix_isolated_official_eps_outliers(stocks)
        payload["meta"]["financials_official_eps_outlier_fix"] = {
            "note": "官方列 EPS 推得股數低於前後兩季（兩季彼此一致、再外一季也一致）平均 >30%，且偏高幅度等於同年較早季 EPS（舊離散化少減一季）"
                    "或官方本益比反推近四季 EPS 證實時，EPS 改成淨利÷相鄰季平均股數，原值存 eps_raw（先.一三五-1mz）",
            "fixed_rows": _of["fixed_rows"], "fixed": _of["fixed"], "left_unverified": _of["left_unverified"],
            "generated_at": datetime.now(TW_TZ).isoformat(), "mode": "daily"}
    except Exception as e:
        print(f"[warn] 官方列 EPS 離群修正失敗：{e}")
        errors.append(f"official_eps_outlier_fix: {e}")
    try:  # 先.一三五-1mx：股數基準持續跳變且官方近四季 EPS 證實時，舊季 EPS 追溯調整；自身失敗只警告（十二節）
        payload["meta"]["financials_share_base_restate"] = _share_base_meta(restate_share_base_shift(stocks), "daily")
    except Exception as e:
        print(f"[warn] 股數基準追溯調整失敗：{e}")
        errors.append(f"share_base_restate: {e}")
    try:  # 先.一三五-1my：面額非 10 元時股本÷10 推的股數會錯，改用推得股數；自身失敗只警告（十二節）
        payload["meta"]["financials_shares_implied_fix"] = _shares_meta(fix_shares_by_implied_eps(stocks), "daily")
    except Exception as e:
        print(f"[warn] 推得股數修正失敗：{e}")
        errors.append(f"shares_implied_fix: {e}")
    try:
        payload["meta"]["roe_cleared_nonconsecutive_codes"] = clear_stale_nonconsecutive_roe(stocks)
    except Exception as e:  # 這道清理自己出錯只記警告，不擋寫檔（十二節）
        print(f"[warn] ROE 連續性複查失敗：{e}")
        errors.append(f"roe_recheck: {e}")
    payload["meta"].setdefault("errors", [])
    payload["meta"]["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：財報更新 {income_updated} 檔，{skipped_no_baseline} 檔因缺同年較早季度"
          f"基準無法安全還原單季數字而跳過（合計 {len(stocks)} 檔有任何資料）")
    if errors:
        print(f"部分失敗（不中止）：{errors}")


if __name__ == "__main__":
    if "--offline-merge-backfill" in sys.argv:
        offline_merge_backfill()
    else:
        main()
