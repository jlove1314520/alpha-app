"""先.一三八-1：停資停券預告表每日累積（TWSE BFI84U＋TPEx tpex_margin_trading_term）。

為什麼要存：兩家官方端點都只給「當下」的預告（先.一三五-1i 查證：TWSE 網頁版忽略日期參數、
TPEx openapi 只有當日），不從今天開始每天存就永遠沒有歷史；候選 N9（股東會停券）要靠它。

- 只在 market.yml 台北 17:13 班跑（已定案，Cowork 收件匣 027），每次 TWSE openapi 1 次＋TPEx openapi 1 次＝每日 2 次。
- 共用 data/rate_limit_state.json（來源名 twse_openapi／tpex_openapi，同源間隔 ≥3 秒，
  402/403/428/429 即標記封鎖 2 小時不重試）；任一邊失敗只略過那一邊。
- 輸出 data/margin_suspension_daily/YYYY-MM-DD.json（台北日期，一天一檔）；當天檔兩邊都已成功就不再送請求。
- 原始欄位照存（另加統一鍵 code／name／start／end／reason，民國日期轉西元），不猜、不補。
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援 reconfigure 時照舊輸出，不中斷
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "margin_suspension_daily"

HEADERS = {"User-Agent": "AlphaApp-MarginSuspension " + (os.environ.get("ALPHA_UA_CONTACT") or "contact@alpha-app-project.example")}

RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
BLOCK_STATUS = (402, 403, 428, 429)

SOURCES = {
    "TWSE": ("twse_openapi", "https://openapi.twse.com.tw/v1/exchangeReport/BFI84U"),
    "TPEX": ("tpex_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading_term"),
}
# 原始欄位 → 統一鍵（先.一三五-1i 實測欄位）
FIELD_MAP = {
    "TWSE": {"Code": "code", "Name": "name", "StartDate": "start", "EndDate": "end", "Reason": "reason"},
    "TPEX": {"SecuritiesCompanyCode": "code", "CompanyName": "name", "ShortSaleSuspensionStartDate": "start",
             "ShortSaleSuspensionEndDate": "end", "Reason": "reason", "Date": "report_date"},
}
DATE_KEYS = ("start", "end", "report_date")


# ---------- 共用節流（與其他 openapi 腳本同一份 rate_limit_state.json） ----------

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
                raise RuntimeError(f"{source} 封鎖冷卻中（還剩約{remain_min}分鐘，原因：{src.get('block_reason', '未知')}），不送請求")
            last = src.get("last_request_at")
            wait = (RATE_LIMIT_MIN_INTERVAL_SEC - (now - last)) if last else 0.0
            if wait <= 0:
                src["last_request_at"] = now
                state["sources"][source] = src
                _save_rate_limit_state(state)
                return
        time.sleep(wait)


def _rate_limit_record_block(*args, **kwargs) -> None:
    """修.FinMind計數：在跨行程鎖內做「重讀→標封鎖→寫回」（參數原樣轉給 _rate_limit_record_block_unlocked）。"""
    with _rate_limit_lock():
        _rate_limit_record_block_unlocked(*args, **kwargs)


def _rate_limit_record_block_unlocked(source: str, status_code: int) -> None:
    # 只記狀態碼，不記回應內文（避免把任何回應片段寫進公開 repo）
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}"
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


# ---------- 解析 ----------

def roc_to_iso(roc) -> str | None:
    """"1151102" → "2026-11-02"；格式不符回 None（不猜）。"""
    s = str(roc or "").strip()
    if not s.isdigit() or len(s) not in (6, 7):
        return None
    try:
        return datetime(int(s[:-4]) + 1911, int(s[-4:-2]), int(s[-2:])).strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalize(rows, market: str) -> tuple[list[dict], list[str]]:
    if not isinstance(rows, list):
        raise RuntimeError(f"{market} 回應不是陣列（{type(rows).__name__}）")
    fmap = FIELD_MAP[market]
    out, warns = [], []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            warns.append(f"{market} 第{i}列不是物件，略過")
            continue
        missing = [k for k in fmap if k not in r]
        if missing:
            warns.append(f"{market} 第{i}列缺欄位 {missing}")
        rec = {"market": market}
        for k, v in fmap.items():
            val = r.get(k)
            rec[v] = val.strip() if isinstance(val, str) else val
        for dk in DATE_KEYS:
            if dk in rec:
                iso = roc_to_iso(rec[dk])
                if rec[dk] and iso is None:
                    warns.append(f"{market} {rec.get('code')} {dk}={rec[dk]!r} 不是民國日期，保留原值")
                rec[dk + "_iso"] = iso
        rec["raw"] = r
        out.append(rec)
    return out, warns


def fetch_one(market: str) -> list:
    source, url = SOURCES[market]
    _rate_limit_wait_or_raise(source)
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code in BLOCK_STATUS:
        _rate_limit_record_block(source, r.status_code)
        raise RuntimeError(f"{source} 回 HTTP {r.status_code}，已標記封鎖 2 小時")
    r.raise_for_status()
    try:
        return json.loads(r.content.decode("utf-8-sig"))
    except ValueError as e:
        raise RuntimeError(f"{source} 回應不是 JSON（可能是 200＋HTML 錯誤頁）：{e}") from e


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.json"
    prior = None
    if out_path.exists():
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"既有 {out_path.name} 讀不回來（{e}），不覆蓋，本次不寫檔")
            return 1
    prior_markets = (prior or {}).get("markets", {})
    todo = [m for m in SOURCES if not (prior_markets.get(m) or {}).get("ok")]
    if not todo:
        print(f"{out_path.name} 兩邊今天都已存過，不再送請求")
        return 0

    markets = dict(prior_markets)
    errors = []
    for market in todo:
        try:
            recs, warns = normalize(fetch_one(market), market)
            markets[market] = {"ok": True, "n": len(recs), "records": recs, "warnings": warns[:20],
                               "source": SOURCES[market][1]}
            print(f"{market}：{len(recs)} 筆" + (f"，警告 {len(warns)} 則" if warns else ""))
        except Exception as e:  # noqa: BLE001 —— 一邊失敗不影響另一邊（只略過）
            errors.append(f"{market}：{e}")
            markets[market] = {"ok": False, "error": str(e)[:300], "source": SOURCES[market][1]}
            print(f"{market} 失敗（略過）：{e}")

    if not any((v or {}).get("ok") for v in markets.values()):
        print("兩邊都沒有資料，不寫檔")
        return 0  # 失敗只略過（已定案提案：不讓排程變紅）
    doc = {
        "_note": "停資停券預告表每日快照（官方只給當下預告，靠每日累積成歷史）。非投資建議。",
        "snapshot_date": today,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "markets": markets,
    }
    if dry:
        print("--dry-run：不寫檔")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
