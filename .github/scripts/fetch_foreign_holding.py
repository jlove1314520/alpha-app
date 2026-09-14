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


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
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
