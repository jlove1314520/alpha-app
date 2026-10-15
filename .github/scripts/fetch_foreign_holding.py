# -*- coding: utf-8 -*-
"""每日排程更新 data/foreign_holding.json（外資及陸資持股比率）。

`PENDING_QUEUE.md`「源頭二.3」（依機構用途強度×接入成本排前10名先接入）第1名：
外資持股水位是機構投資人最常用的籌碼指標之一（外資加碼/減碼個股），資料源是
TWSE 官方公開端點、已在同一台主機（`www.twse.com.tw`）用同一套 rwd 路徑慣例
（跟 T86／MI_MARGN／TWTASU／BFIAUU 同一組，見 `docs/DATA_SOURCE_MAP.md`「共通
結論」：除 `/epaper/`、`/FTSE/` 外全站允許），接入成本低、不需要新的合規查證。

端點：`https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS`
**已知地雷（本次實測踩到，記錄避免下次重踩）**：`selectType` 參數必須是
`ALLBUT0999`（TWSE 官方慣例代碼，排除大盤加總列）才會回傳逐股資料；
`selectType=ALL` 會回傳 `data:[]`（0 筆），不是端點失敗，是這個特定站點的
`selectType` 語意跟 T86（`selectType=ALL` 即為全部）不同，不能沿用同一個
慣例值，2026-09-15 用 curl 實測多組 selectType 值才找到 `ALLBUT0999` 才有效。

輸出欄位（原始官方中文欄名 → 本檔案 key）：
- 全體外資及陸資持股比率 → foreign_holding_ratio（%）
- 外資及陸資尚可投資比率 → foreign_can_invest_ratio（%）
- 發行股數 → shares_issued
- 全體外資及陸資持有股數 → foreign_shares_held

跟 `fetch_market_tw.py` 的 T86 一樣同屬 `www.twse.com.tw/rwd` 家族，保守起見
採同一套節流慣例：跨 process 共用節流狀態（`data/rate_limit_state.json`）、
單次嘗試不重試（重試可能加重被判定為異常流量的風險）、找不到今天資料時往前
回退（假日/尚未定案），最多回退 5 個自然日。
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
OUT_PATH = REPO_ROOT / "data" / "foreign_holding.json"
TW_TZ = timezone(timedelta(hours=8))

MI_QFIIS_URL = "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS"
MAX_LOOKBACK_DAYS = 5

RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
SOURCE = "twse_mi_qfiis"


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


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def fetch_mi_qfiis(date_str: str) -> dict | None:
    """打一次 MI_QFIIS，回傳 {code: {...}}；當天沒有定案資料回傳 None（呼叫端
    自行決定要不要往前回退），不是例外——這是正常的「今天還沒有資料」狀態。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
    }
    _rate_limit_wait_or_raise(SOURCE)
    r = requests.get(
        MI_QFIIS_URL,
        params={"response": "json", "date": date_str, "selectType": "ALLBUT0999"},
        headers=headers, timeout=20,
    )
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block(SOURCE, r.status_code, r.text[:200])
        raise RuntimeError(f"{SOURCE}回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return None
    fields = body["fields"]
    idx = {name: i for i, name in enumerate(fields)}
    need = ["證券代號", "發行股數", "全體外資及陸資持有股數",
            "外資及陸資尚可投資比率", "全體外資及陸資持股比率"]
    if not all(n in idx for n in need):
        raise RuntimeError(f"{SOURCE}回應欄位跟預期不符：{fields}")

    def _num(v):
        if v in (None, "", "--"):
            return None
        try:
            return float(str(v).replace(",", ""))
        except ValueError:
            return None

    out: dict[str, dict] = {}
    for row in body["data"]:
        code = (row[idx["證券代號"]] or "").strip()
        if not code:
            continue
        out[code] = {
            "date": date_str,
            "shares_issued": _num(row[idx["發行股數"]]),
            "foreign_shares_held": _num(row[idx["全體外資及陸資持有股數"]]),
            "foreign_can_invest_ratio": _num(row[idx["外資及陸資尚可投資比率"]]),
            "foreign_holding_ratio": _num(row[idx["全體外資及陸資持股比率"]]),
        }
    return out or None


def main() -> int:
    now_tw = datetime.now(TW_TZ)
    company_info = (_load(REPO_ROOT / "data" / "company_info.json", {}) or {}).get("companies") or {}

    stocks = None
    used_date = None
    err = None
    for back in range(MAX_LOOKBACK_DAYS + 1):
        d = (now_tw - timedelta(days=back)).strftime("%Y%m%d")
        try:
            stocks = fetch_mi_qfiis(d)
        except Exception as e:
            err = e
            print(f"MI_QFIIS {d} 失敗：{e}")
            break  # 節流/斷路例外不重試多天，避免疊加請求
        if stocks:
            used_date = d
            break
        print(f"MI_QFIIS {d} 無資料（可能非交易日或尚未定案），往前回退一天")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "TWSE官方 rwd/zh/fund/MI_QFIIS（外資及陸資投資持股統計，免金鑰）",
        "url": MI_QFIIS_URL,
        "errors": [str(err)] if err else [],
        "stocks": {},
    }
    if stocks:
        for code, rec in stocks.items():
            name = (company_info.get(code) or {}).get("name")
            out["stocks"][code] = {**rec, "name": name}
        print(f"foreign_holding.json：{len(out['stocks'])} 檔，資料日 {used_date}")
    else:
        # 抓不到當次資料時保留舊檔（若有），避免用空狀態覆蓋掉昨天的有效資料。
        prior = _load(OUT_PATH)
        if prior and prior.get("stocks"):
            print(f"本次無新資料，保留既有 {len(prior['stocks'])} 檔（資料日 {next(iter(prior['stocks'].values()), {}).get('date')}）")
            return 0
        print("本次無新資料，且沒有既有檔案可保留")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0 if stocks else 1


if __name__ == "__main__":
    raise SystemExit(main())
